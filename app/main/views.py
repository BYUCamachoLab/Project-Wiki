import os
import re
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import request, redirect, render_template, \
    url_for, flash, send_from_directory
from flask_login import current_user
from mongoengine import DoesNotExist
from mongoengine.context_managers import switch_db
from bs4 import BeautifulSoup

from . import main
from .. import config, basedir, wiki_md
from .forms import BasicEditForm, WikiEditForm, SearchForm, CommentForm,\
    RenameForm, UploadForm, VersionRecoverForm
from ..models import Permission, WikiGroup, WikiComment, WikiPage, WikiFile, WikiCache, \
    WikiPageTree, render_wiki_file, render_wiki_image
from ..email import send_email
from ..wiki_util.pagination import calc_page_num

from ..decorators import admin_required, user_required, guest_required


def _collect_tree_ids(nodes):
    """Recursively collect all page id strings from a nested tree list."""
    for node in nodes:
        yield node['id']
        yield from _collect_tree_ids(node.get('children', []))


def _add_pages_to_tree(group, parent_id, new_ids):
    """Insert new_ids as children of parent_id in the group's WikiPageTree.

    Pages already present anywhere in the tree are skipped (first-placement wins).
    Silently no-ops if no WikiPageTree exists yet.
    """
    with switch_db(WikiPageTree, group) as _WikiPageTree:
        tree_doc = _WikiPageTree.objects.first()
        if tree_doc is None:
            return

        existing_ids = set(_collect_tree_ids(tree_doc.tree)) | set(tree_doc.orphans)
        to_add = [pid for pid in new_ids if pid not in existing_ids]
        if not to_add:
            return

        def insert_into(nodes, target_parent_id, child_ids):
            for node in nodes:
                if node['id'] == target_parent_id:
                    for cid in child_ids:
                        node.setdefault('children', []).append(
                            {'id': cid, 'children': []})
                    return True
                if insert_into(node.get('children', []), target_parent_id, child_ids):
                    return True
            return False

        inserted = insert_into(tree_doc.tree, parent_id, to_add)
        if not inserted:
            # parent not found in tree — put new pages in orphans
            tree_doc.orphans.extend(to_add)

        tree_doc.save()


def wiki_render_template(template, group, *args, current_page_id=None, **kwargs):
    with switch_db(WikiPageTree, group) as _WikiPageTree, \
            switch_db(WikiPage, group) as _WikiPage:
        page_tree = _WikiPageTree.objects.first()

        if page_tree is not None:
            all_ids = list(_collect_tree_ids(page_tree.tree)) + list(page_tree.orphans)
            pages = _WikiPage.objects(id__in=all_ids).only('id', 'title')
            page_id_title_map = {str(p.id): p.title for p in pages}
        else:
            page_id_title_map = {}

        return render_template(template, group=group,
                               page_tree=page_tree,
                               page_id_title_map=page_id_title_map,
                               current_page_id=current_page_id,
                               *args, **kwargs)


@main.route('/')
def index():
    all_groups = WikiGroup.objects(active=True).all()
    return render_template('cover.html', all_groups=all_groups)


@main.route('/<group>/search', methods=['GET', 'POST'])
@guest_required
def search(group):
    """Search text on wiki page, `weights{ title:10, content:2, comment:1 }`
    """
    search_keyword = request.args.get('search')
    result_page = request.args.get('page', default=1, type=int)
    form = SearchForm(search=search_keyword)
    results, start_page, end_page = None, None, None
    if search_keyword and not search_keyword.isspace():
        with switch_db(WikiPage, group) as _WikiPage:
            results = _WikiPage.objects.search_text(search_keyword). \
                only('id', 'title', 'modified_on', 'modified_by'). \
                order_by('$text_score').paginate(page=result_page, per_page=100)
        start_page, end_page = calc_page_num(result_page, results.pages)

    if form.validate_on_submit():
        return redirect(url_for('.search', group=group, search=form.search.data))
        
    try:
        total_pages = results.pages
    except AttributeError:
        total_pages = 0
    return wiki_render_template('search.html', 
                                group=group, 
                                form=form, 
                                results=results,
                                start_page=start_page, 
                                end_page=end_page,
                                total_pages=total_pages)


@main.route('/<group>/keypage-edit', methods=['GET', 'POST'])
@admin_required
def wiki_keypage_edit(group):
    with switch_db(WikiCache, group) as _WikiCache:
        _cache = _WikiCache.objects.first()
        _keypage_titles = [i[1] for i in _cache.keypages_id_title]
        form = BasicEditForm(textArea='\n'.join(_keypage_titles))
        if form.validate_on_submit():
            new_titles = form.textArea.data.splitlines()
            _cache.update_keypages(group, *new_titles)
            return redirect(url_for('.wiki_group_home', group=group))
    return wiki_render_template('wiki_keypage_edit.html', group=group, form=form)


@main.route('/<group>/changes')
@guest_required
def wiki_show_changes(group):
    with switch_db(WikiPage, group) as _WikiPage, \
            switch_db(WikiCache, group) as _WikiCache:
        _cache = _WikiCache.objects.only('changes_id_title').first()
        changed_pages = []
        for _id, pageTitle in _cache.changes_id_title[::-1]:
            try:
                changed_pages.append(_WikiPage.objects.\
                    only('id', 'title', 'modified_by', 'modified_on').get(id=_id))
            except DoesNotExist:
                # TODO: handle it rather than ignore it
                pass
    return wiki_render_template('wiki_changes.html',
                                group=group,
                                changed_pages=changed_pages)


@main.route('/<group>/<page_id>/page', methods=['GET', 'POST'])
@guest_required
def wiki_page(group, page_id):
    form = CommentForm()

    if form.validate_on_submit() and current_user.can(group, Permission.WRITE):
        _, comment_html = wiki_md(group, form.textArea.data, is_comment=True)
        new_comment = WikiComment(
            id='{}-{}'.format(datetime.utcnow().strftime('%s'), current_user.id),
            author=current_user.name,
            html=comment_html,
            md=form.textArea.data
        )
        with switch_db(WikiPage, group) as _WikiPage, \
                switch_db(WikiCache, group) as _WikiCache:
            _WikiPage.objects(id=page_id).update_one(push__comments=new_comment)
            page = _WikiPage.objects.only('id', 'title').get_or_404(id=page_id)
            _cache = _WikiCache.objects.only('changes_id_title').first()
            _cache.add_changed_page(page.id, page.title, datetime.now())

            user_emails = [u.email for u in wiki_md.users_to_notify]
            send_email(user_emails, 'You are mentioned', 
                       '{} ({}) mentioned you at <a href="{}#wiki-comment-box">{}</a>'.\
                       format(current_user.name, 
                              current_user.email, 
                              request.base_url, 
                              page.title))
            return redirect(url_for('.wiki_page', 
                                    group=group, 
                                    page_id=page_id, 
                                    _anchor='wiki-comment-box'))

    with switch_db(WikiPage, group) as _WikiPage:
        page = _WikiPage.objects.exclude('md', 'refs', 'files').get_or_404(id=page_id)
    return wiki_render_template('wiki_page.html', group=group, page=page, form=form,
                                current_page_id=str(page.id))


href_prog = re.compile(r'\/(.+?)\/([0-9a-f]{24})\/page(#.*)?')


@main.route('/<group>/<page_id>/edit', methods=['GET', 'POST'])
@user_required
def wiki_page_edit(group, page_id):
    with switch_db(WikiPage, group) as _WikiPage:
        page = _WikiPage.objects.exclude('html', 'comments').get_or_404(id=page_id)
        form = WikiEditForm(current_version=page.current_version)
        upload_form = UploadForm()

        if form.validate_on_submit():
            if form.current_version.data == page.current_version:
                # Capture old refs before processing (None-guard for deleted pages)
                old_ref_ids = {str(r.id) for r in (page.refs or []) if r is not None}

                toc, html = wiki_md(group, form.textArea.data)
                page.update_content(group, form.textArea.data, html, toc)

                # Make sure wiki page references using raw html are also kept track of.
                soup = BeautifulSoup(form.textArea.data, 'html.parser')
                hrefs = [a['href'] for a in soup.find_all('a', class_='wiki-page')]
                for href in hrefs:
                    m = href_prog.fullmatch(href)
                    try:
                        href_group, href_page_id = m.group(1), m.group(2)
                        assert group == href_group
                        href_page = _WikiPage.objects(id=href_page_id).only('id').first()
                        if href_page:
                            wiki_md.wiki_refs.append(href_page)
                    except (AttributeError, AssertionError):
                        pass

                _WikiPage.objects(id=page.id).update(set__refs=wiki_md.wiki_refs,
                                                     set__files=wiki_md.wiki_files)

                # Add newly linked pages as children of this page in the tree
                new_ref_ids = {str(r.id) for r in wiki_md.wiki_refs}
                added_ids = new_ref_ids - old_ref_ids
                if added_ids:
                    _add_pages_to_tree(group, str(page.id), added_ids)

                return redirect(url_for('.wiki_page', group=group, page_id=page_id))
            else:
                flash('Other changes have been made to this '
                      'page since you started editing it.')
    return wiki_render_template('wiki_page_edit.html', 
                                group=group, 
                                page=page, 
                                form=form, 
                                upload_form=upload_form)


@main.route('/<group>/<page_id>/upload')
@user_required
def wiki_upload_file(group, page_id):
    form = UploadForm()
    return render_template('wiki_upload_file.html', 
                           group=group,
                           form=form,
                           page_id=page_id)


@main.route('/do-upload/<group>', methods=['POST'])
@user_required
def wiki_do_upload(group):
    """Handle the ajax upload request from a normal page.
    Since every uploaded file is renamed to its id in database,
    There is no need to secure its filename during uploading.
    However, users should try to upload files with a secure 
    filename, namely using ascii encoding and normal characters. 
    
    Since storage is cheap, a secured filename is also saved in 
    `WikiFile` such that there is no need to run `secure_filename` 
    each time a file is requested. 
    """
    form = request.form

    with switch_db(WikiPage, group) as _WikiPage:
        page_id = form.get('page_id', None)
        parent_page = _WikiPage.objects.exclude('comments', 'refs').get(id=page_id)

        file_md = ''
        file_html = ''
        for i, file in enumerate(request.files.getlist("file")):
            # save uploaded file info to database
            wiki_file = WikiFile(name=file.filename,
                                 secured_name=secure_filename(file.filename),
                                 mime_type=file.mimetype,
                                 uploaded_by=current_user.name)

            file.save(os.path.join(config.UPLOAD_FOLDER, group, str(wiki_file.id)))

            # Use the position of file pointer to get file size
            wiki_file.size = file.tell()
            wiki_file.switch_db(group).save()

            if 'image' in file.mimetype:
                file_md += '\n\n[image:{}]'.format(wiki_file.id)
                file_html += '<p>{}</p>'.\
                    format(render_wiki_image(group, wiki_file.id, wiki_file.name))
            else:
                file_md += '\n\n[file:{}]'.format(wiki_file.id)
                file_html += '<p>{}</p>'.\
                    format(render_wiki_file(group, wiki_file.id, wiki_file.name))
            parent_page.files.append(wiki_file)

        parent_page.update_content(group, 
                                   parent_page.md+file_md,
                                   parent_page.html+file_html,
                                   parent_page.toc)
    return ''


@main.route('/do-upload/from-edit/<group>', methods=['POST'])
@user_required
def wiki_do_upload_from_edit(group):
    """Handle the ajax upload request from an editing page.
    Since every uploaded file is renamed to its id in database,
    There is no need to secure its filename during uploading.
    However, users should try to upload files with a secure 
    filename, namely using ascii encoding and normal characters. 
    
    Since storage is cheap, a secured filename is also saved in 
    `WikiFile` such that there is no need to run `secure_filename` 
    each time a file is requested.
    """
    file_md = ''
    for i, file in enumerate(request.files.getlist("file")):
        # save uploaded file info to database
        wiki_file = WikiFile(name=file.filename,
                             secured_name=secure_filename(file.filename),
                             mime_type=file.mimetype,
                             uploaded_by=current_user.name)

        # save the uploaded file to server
        file.save(os.path.join(config.UPLOAD_FOLDER, group, str(wiki_file.id)))

        # Use the position of file pointer to get file size
        wiki_file.size = file.tell()
        wiki_file.switch_db(group).save()

        # update the page where the files are uploaded to
        file_type = 'image' if 'image' in file.mimetype else 'file'
        file_md += '\n\n[{}:{}]'.format(file_type, wiki_file.id)
    return file_md


@main.route('/<group>/<page_id>/versions', methods=['GET', 'POST'])
@user_required
def wiki_page_versions(group, page_id):
    with switch_db(WikiPage, group) as _WikiPage:
        page = _WikiPage.objects.exclude('html', 'comments').get_or_404(id=page_id)
        if page.current_version == 1:
            return redirect(url_for('.wiki_page', group=group, page_id=page_id))
        form = VersionRecoverForm()
        if form.validate_on_submit():
            if form.version.data >= page.current_version:
                flash('Please enter an old version number.')
            else:
                recovered_content = page.get_version_content(group, form.version.data)
                toc, html = wiki_md(group, recovered_content)
                page.update_content(group, recovered_content, html, toc)
                _WikiPage.objects(id=page.id).update(add_to_set__refs=wiki_md.wiki_refs,
                                                     add_to_set__files=wiki_md.wiki_files)
                return redirect(url_for('.wiki_page', group=group, page_id=page_id))

    old_ver_num = request.args.get('version', default=page.current_version - 1, type=int)
    new_ver_num = old_ver_num + 1
    diff_table = page.make_wikipage_diff(group, old_ver_num, new_ver_num)

    start_page, end_page = calc_page_num(old_ver_num, page.current_version-1)

    return wiki_render_template('wiki_page_versions.html', 
                                group=group, 
                                page=page, 
                                form=form,
                                old_ver_num=old_ver_num, 
                                new_ver_num=new_ver_num, 
                                diff_table=diff_table,
                                start_page=start_page, 
                                end_page=end_page,
                                total_pages=page.current_version-1)


@main.route('/<group>/<page_id>/rename', methods=['GET', 'POST'])
@user_required
def wiki_rename_page(group, page_id):
    with switch_db(WikiPage, group) as _WikiPage:
        page = _WikiPage.objects.only('id', 'title').get_or_404(id=page_id)
        if page.title == 'Home':
            return redirect(url_for('.wiki_group_home', group=group))

        form = RenameForm(new_title=page.title)
        if form.validate_on_submit():
            from flask import jsonify as _jsonify
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            new_title = form.new_title.data
            if page.title == new_title:
                if is_ajax:
                    return _jsonify({'ok': False, 'error': 'The page name is not changed.'})
                flash('The page name is not changed.')
            elif _WikiPage.objects(title=new_title).count() > 0:
                if is_ajax:
                    return _jsonify({'ok': False, 'error': 'That title is already taken.'})
                flash('The new page title has already been taken.')
            else:
                page.rename(group, new_title)
                if is_ajax:
                    return _jsonify({'ok': True, 'new_title': new_title})
                return redirect(url_for('.wiki_page', group=group, page_id=page_id))

    return wiki_render_template('wiki_rename_page.html', group=group, page=page, form=form)


@main.route('/<group>/<page_id>/references')
@guest_required
def wiki_references(group, page_id):
    with switch_db(WikiPage, group) as _WikiPage:
        page = _WikiPage.objects.only('title').get_or_404(id=page_id)
        referenced_by = _WikiPage.objects(refs__contains=page_id).\
            only('id', 'title').all()
    # The pages which reference `page`
    return wiki_render_template('wiki_references.html', 
                                group=group, 
                                page=page,
                                referenced_by=referenced_by)


@main.route('/<group>/file/<int:file_id>')
@guest_required
def wiki_file(group, file_id):
    """Uploaded files are saved on server with their 
    database id as filename, so filenames are secured 
    when user try to download. 
    """
    fn = request.args.get('filename')
    if not fn:
        with switch_db(WikiFile, group) as _WikiFile:
            wiki_file = _WikiFile.objects.get_or_404(id=file_id)
            fn = wiki_file.secured_name
    return send_from_directory(os.path.join(config.UPLOAD_FOLDER, group),
                               str(file_id),
                               as_attachment=True,
                               attachment_filename=fn)


@main.route('/<group>/')
@main.route('/<group>/home')
@guest_required
def wiki_group_home(group):
    with switch_db(WikiPage, group) as _WikiPage:
        wiki_group_homepage = _WikiPage.objects(title='Home').only('id').first()
        return redirect(url_for('.wiki_page', 
                                group=group, 
                                page_id=str(wiki_group_homepage.id)))


@main.route('/<group>/structure')
@admin_required
def wiki_structure(group):
    return wiki_render_template('structure.html', group=group)


@main.route('/<group>/structure/save', methods=['POST'])
@admin_required
def wiki_structure_save(group):
    from flask import jsonify
    data = request.get_json(silent=True)
    if not data or 'tree' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    new_tree    = data.get('tree', [])
    new_orphans = data.get('orphans', [])

    # Validate all referenced IDs exist in this group
    all_ids = list(_collect_tree_ids(new_tree)) + new_orphans
    with switch_db(WikiPage, group) as _WikiPage:
        existing_ids = {str(p.id) for p in _WikiPage.objects(id__in=all_ids).only('id')}
    invalid = [i for i in all_ids if i not in existing_ids]
    if invalid:
        return jsonify({'error': 'Unknown page IDs: ' + ', '.join(invalid[:5])}), 400

    with switch_db(WikiPageTree, group) as _WikiPageTree:
        tree_doc = _WikiPageTree.objects.first()
        if tree_doc:
            tree_doc.tree    = new_tree
            tree_doc.orphans = new_orphans
            tree_doc.save()
        else:
            _WikiPageTree(tree=new_tree, orphans=new_orphans).save()

    return jsonify({'ok': True})


@main.route('/<group>/markdown')
@guest_required
def wiki_markdown_instruction(group):
    return wiki_render_template('wiki_markdown.html', group=group)
