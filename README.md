# git_revision
A plugin that integrates Git with Pelican.

If not available in the content's metadata, `git_revision` will set the added and modified date for each page and
article that is version controlled by Git. All previous revisions of the content will also be written and accessible by
using the `git` object attached to each content object. The full information contained in the commit and the file path
relative to the Git repository, are also accessible.

See the [usage](#Usage) section for more details and a working example.


# Requirements
`git_revision` requires [GitPython](https://github.com/gitpython-developers/GitPython).

    pip install GitPython


# Details
The URLs generated by the plugin will look like this: `{SITEURL}/<name>/<hexsha>/`, where name is the last component of
the original content's URL and hexsha the commit checksum provided by git in a hex version. To clarify:

* `{SITEURL}/article/` -> `{SITEURL}/article/<hexsha>/`
* `{SITEURL}/article.html` -> `{SITEURL}/article/<hexsha>/`

Currently this behavior is hardcoded but easily adjustable in the source.


# Usage
The `git` object has the following attributes:

* commit: a GitPython [Objects.Commit][0] object
* file_path: The path of the file in relation to the repository path
* revisions: A list of all other revisions for this content
* previous_revision: None or a reference to the previous revision for this content
* next_revision: None or a reference to the next revision for this content


Here's an example on how you can use it in a Jinja2 template:


```html
{% if article.git %}
{% set commit = article.git.commit %}
<div class="container row-fluid">
    {% set previous_revision = article.git.previous_revision %}
    {% if previous_revision %}
    <a href="{{ SITEURL }}/{{ previous_revision.url }}">«</a>
    {% else %}
    «
    {% endif %}

    <a class="btn btn-link" data-toggle="collapse" data-target="#revision">{{ commit.hexsha|truncate(7, end='') }}</a>

    {% set next_revision = article.git.next_revision %}
    {% if next_revision %}
    <a href="{{ SITEURL }}/{{ next_revision.url }}">»</a>
    {% else %}
    »
    {% endif %}
    <div id="revision" class="collapse">
        <p>{{ commit.summary|e }}</p>
        {% set statistics = commit.stats.files[article.git.file_path] %}
        {{ statistics.lines }} lines changed:
        <ul>
            <li><span style="color: green">{{ statistics.insertions }} insertions(+)</span></li>
            <li><span style="color: red">{{ statistics.deletions }} deletions(-)</span></li>
        </ul>
    </div>
</div>
{% endif %}
```


# Credits
Thanks to [Avaris][1] and [winlu][2] in the [#pelican][3] channel for helpful suggestions and helping me figuring out
Pelican's internals quickly.


[0]: http://gitpython.readthedocs.org/en/stable/reference.html#module-git.objects.commit
[1]: https://github.com/avaris
[2]: https://github.com/ingwinlu
[3]: irc://irc.freenode.net/#pelican
