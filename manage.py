from app import create_app, db, wiki_pwd, mail
from app.models import WikiUser, WikiPage, WikiGroup, WikiPageTree
from flask_script import Manager, Shell, Option
from mongoengine.context_managers import switch_db

app = create_app()
manager = Manager(app)


def make_shell_context():
    return dict(app=app, db=db, WikiUser=WikiUser, WikiPage=WikiPage, mail=mail)
manager.add_command('shell', Shell(make_context=make_shell_context))


@manager.option('--force', action='store_true', dest='force', default=False,
                help='Re-seed the tree even if one already exists')
def migrate_page_tree(force):
    """Seed WikiPageTree for each group from the Home page link graph."""
    groups = WikiGroup.objects.all()
    if not groups:
        print('No groups found.')
        return

    for group in groups:
        gname = group.name_no_whitespace
        print(f'Processing group: {gname}')

        with switch_db(WikiPageTree, gname) as _WikiPageTree, \
                switch_db(WikiPage, gname) as _WikiPage:

            existing = _WikiPageTree.objects.first()
            if existing and not force:
                print(f'  Skipping — tree already exists (use --force to re-seed)')
                continue

            # Find Home page
            home = _WikiPage.objects(title='Home').first()
            if home is None:
                print(f'  WARNING: No Home page found, skipping.')
                continue

            # BFS from Home's refs
            tree = []
            orphan_ids = set()
            # Pre-seed visited with Home so it never appears as a tree node
            visited = {str(home.id)}

            def collect_ids(nodes):
                """Walk a nested tree list and collect all ids."""
                for node in nodes:
                    yield node['id']
                    yield from collect_ids(node.get('children', []))

            def build_children(page):
                children = []
                refs = [r for r in (page.refs or []) if r is not None]
                for ref in refs:
                    ref_id = str(ref.id)
                    if ref_id in visited:
                        continue
                    visited.add(ref_id)
                    # Skip dangling refs (target page was deleted)
                    ref_page = _WikiPage.objects(id=ref_id)\
                        .only('id', 'refs').first()
                    if ref_page is None:
                        continue
                    children.append({'id': ref_id,
                                     'children': build_children(ref_page)})
                return children

            # Seed top-level from Home's refs
            home_refs = [r for r in (home.refs or []) if r is not None]
            for ref in home_refs:
                ref_id = str(ref.id)
                if ref_id in visited:
                    continue
                visited.add(ref_id)
                ref_page = _WikiPage.objects(id=ref_id)\
                    .only('id', 'refs').first()
                if ref_page is None:
                    continue
                tree.append({'id': ref_id,
                             'children': build_children(ref_page)})

            # All remaining pages (not Home, not visited) go to orphans
            all_pages = _WikiPage.objects.only('id', 'title').all()
            for page in all_pages:
                pid = str(page.id)
                if pid not in visited and page.title != 'Home':
                    orphan_ids.add(pid)

            orphans = list(orphan_ids)

            if existing and force:
                existing.tree = tree
                existing.orphans = orphans
                existing.save()
            else:
                _WikiPageTree(tree=tree, orphans=orphans).save()

            tree_count = len(list(collect_ids(tree)))
            print(f'  Done — {tree_count} pages in tree, {len(orphans)} orphans')


@manager.command
def create_admin():
    WikiUser(name=app.config['ADMIN_USERNAME'],
             email=app.config['ADMIN_EMAIL'],
             password_hash=wiki_pwd.hash(app.config['ADMIN_PASSWORD']),
             permissions={'super': 0xff}).save()

if __name__ == '__main__':
    manager.run()
