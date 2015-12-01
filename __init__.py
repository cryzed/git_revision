import collections
import functools
import os
import posixpath
import tempfile

import git
import pelican
import pelican.contents
import pelican.generators
import pelican.readers

git_class = collections.namedtuple('git', ('commit', 'file_path', 'revisions', 'previous_revision', 'next_revision'))


@functools.lru_cache(None)
def discover_repository(path):
    root, tail = path, None
    while tail or tail is None:
        try:
            return git.Repo(root)
        except git.InvalidGitRepositoryError:
            root, tail = os.path.split(root)


def make_repository_file_path(repository, path):
    relative_path = os.path.relpath(path, repository.working_dir)
    return relative_path.replace('\\', '/')


def on_content_object_init(content):
    if isinstance(content, pelican.contents.Static):
        return

    source_path = content.source_path
    repository = discover_repository(os.path.dirname(source_path))
    if not repository:
        return

    repository_file_path = make_repository_file_path(repository, source_path)
    commits = list(repository.iter_commits(paths=repository_file_path))

    # Make the list of commits more intuitive to work with
    commits.reverse()

    if not commits:
        return

    first_commit = commits[0]
    latest_commit = commits[-1]

    # This is a revision, always overwrite the published and updated date
    if hasattr(content, 'git'):
        created = pelican.utils.SafeDatetime.fromtimestamp(content.git.commit.authored_date)
        content.date = created
        content.locale_date = pelican.utils.strftime(created, content.date_format)

        previous_revision = content.git.previous_revision
        if not previous_revision:
            return

        # The next revision isn't available at this point, only previous ones due to the order in which Pelican's
        # content_object_init signal is sent. Instead the modified date of the previous revision is set to the created
        # date of this one
        previous_revision.modified = created
        previous_revision.locale_modified = pelican.utils.strftime(created, content.date_format)

        # The current content is a revision, skip creating and setting the git object, since it was already done when
        # processing the first article
        return

    # TODO: Possibly add configuration values to override this behavior
    if not hasattr(content, 'date'):
        created = pelican.utils.SafeDatetime.fromtimestamp(first_commit.authored_date)
        content.date = created
        content.locale_date = pelican.utils.strftime(created, content.date_format)

    if first_commit != latest_commit and not hasattr(content, 'modified'):
        modified = pelican.utils.SafeDatetime.fromtimestamp(latest_commit.authored_date)
        content.modified = modified
        content.locale_modified = pelican.utils.strftime(modified, content.date_format)

    readers = pelican.readers.Readers(content.settings)
    revisions = []
    for commit in commits:
        blob = commit.tree / repository_file_path
        format_ = os.path.splitext(repository_file_path)[1][1:]

        file_descriptor, path = tempfile.mkstemp()
        with os.fdopen(file_descriptor, 'wb') as file:
            file.write(blob.data_stream.read())

        revision = readers.read_file(
            content.settings['PATH'], path, content.__class__, format_, context=content._context
        )
        revision.source_path = content.source_path

        filename = os.path.basename(content.save_as)
        root, extension = os.path.splitext(filename)
        url = content.url

        # This will create URLs in the following format: "<root>/<hexsha>/", where <root> is the last component of the
        # original path with its extension stripped (if available)
        revision.override_save_as = posixpath.join(
            url if url.endswith('/') else posixpath.dirname(url), root if root != 'index' else '', commit.hexsha,
            'index' + extension
        )
        revision.override_url = posixpath.dirname(revision.save_as)

        revisions.append(revision)

    revision_count = len(revisions)
    for index, (commit, revision) in enumerate(zip(commits, revisions)):
        previous_revision = revisions[index-1] if index > 0 else None

        # If this is the second to last revision, point next_revision to the actually generated content instead.
        # Expected behavior is to be directed to the original content URL when attempting to navigate to the latest
        # revision
        next_revision = content if index == revision_count-2 else (
            revisions[index+1] if index < revision_count-1 else None
        )

        revision.git = git_class(commit, repository_file_path, revisions, previous_revision, next_revision)

        # TODO: Find a way to prevent sending this signal twice (previously sent during creation with read_file)
        pelican.signals.content_object_init.send(revision)

    # There's only an actual previous revision if there was more than one commit, i.e. more than one revision
    previous_revision = revisions[-2] if revision_count > 1 else None
    content.git = git_class(latest_commit, repository_file_path, revisions, previous_revision, None)


def on_content_writer_finalized(content_type, generator, writer):
    contents = generator.articles if content_type == 'article' else generator.pages
    write = functools.partial(
        writer.write_file, context=generator.context, relative_urls=generator.settings['RELATIVE_URLS']
    )

    for content in contents:
        if not hasattr(content, 'git'):
            continue

        for revision in content.git.revisions:
            write(**{
                'name': revision.save_as,
                'template': generator.get_template(revision.template),
                content_type: revision,
                'category': revision.category
            })


on_article_writer_finalized = functools.partial(on_content_writer_finalized, 'article')
on_page_writer_finalized = functools.partial(on_content_writer_finalized, 'page')


def register():
    pelican.signals.content_object_init.connect(on_content_object_init)
    pelican.signals.article_writer_finalized.connect(on_article_writer_finalized)
    pelican.signals.page_writer_finalized.connect(on_page_writer_finalized)
