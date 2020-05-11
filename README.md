# A file format to record exact dependencies of a project

This document proposes a file format to store the exact dependencies of a
software. The file format is intended to primarily serve as the “lock file”
format for projects using standard Python packaging tooling, but also
extendable for declaring dependencies from alternative package management
systems.


## Terminology

### Project

A collection of code that may require some common other projects available in
the same runtime environment in order to function. Typical examples of a
project include:

* A Django website, which needs certain versions of the Python distribution
  `Django` installed in the environment.
* A Python package that is intended to be `import`-ed, which imports other
  Python packages that need to be installed in the same environment as itself.
* A Python script that `import`s third-party Python packages, that need to be
  installed in the Python environment to run it.
* A Python virtual environment with specific versions of third-party packages
  used to reproduce results in Jupyter notebooks.

### Dependency

A prerequisite for a project to successfully run. This may be either a “direct”
dependency, which the project directly references (e.g. by `import`), or
“transitive” dependency, which is not directly referenced by a project, but
still required because it is referenced by one of the project’s direct
dependencies or other transitive dependencies.


### Meta-dependency

A dependency that is automatically satisfied if all of its dependencies are
satisfied.


### Lock file

A file that contains all required information to produce the full dependency
for a project.


## Structure

### Specifying dependencies

Top-level key `dependencies` point to a mapping, which contain all
dependencies of this project. Here is one example (nested contents skipped for
brevity; they will be discussed in later sections):

```json
{
    "dependencies": {
        "": { ... },
        "[test]": { ... },
        "appdirs": { ... },
        "contextlib": { ... },
        "distlib": { ... },
        "filelock": { ... },
        "importlib-resources": { ... },
        "importlib-metadata": { ... },
        "pathlib2": { ... },
        "six": { ... },
        "virtualenv": { ... }
    }
}
```

Each key in the mapping is a string that identifies a dependency. The key does
not hold any special meaning itself, but the key is used to refer the dependency it maps
to and should be unique in the lock file.

Four key patterns are reserved with special meanings by Python packaging:

1. A valid “normalized name” as specified by [PEP 503], i.e. satisfying regular
   expression `^[a-z0-9][-a-z0-9]*$`. A dependency using such key should be
   satisfied by installating a Python distribution with name matching the key.
2. A valid normalized name followed a literal `;` (semicolon) sign, and one or
   more ASCII numerical digits, i.e. satisfying regular expression
   `^[a-z0-9][-a-z0-9]*;[0-9]+$`. A dependency using such key should be
   satisfied by installating a Python distribution with name matching the part
   of the key before `;`.
3. An empty string. This dependency should be a meta-dependency that contains
   *only* essential direct dependencies of the project, similar to Setuptools’
   `installs_require` entries.
4. A valid normalized name surrounded by a pair square brackets, i.e.
   satisfying regular expression `^\[[a-z0-9][-a-z0-9]*\]$`. A dependency
   using such key should be a meta-dependency that points optional direct
   dependencies of the project, similar to Setuptools’s `extra_requires`
   entries.

The second pattern is reserved to support cases where a Python distribution
needs to be specified differently depend on the platform. For example,
[docutils 0.15] only supports Python 3, while Python 2 support is available as
0.15.post1. This pattern allows the lock file to conditionally use
`docutils@0` for 0.15, and `docutils@1` for 0.15.post1.


### Satisfying a dependency

Each value in the `dependencies` mapping should be a mapping. A dependency is
satisfied if all entries in this mapping are satisfied.

Here is the `virtualenv` entry in the above example:

```json
{
    "dependencies": {
        "appdirs": null,
        "contextlib": "python_version < '3.3'",
        "distlib": null,
        "filelock": null,
        "importlib-resources": "python_version < '3.7'",
        "importlib-metadata": "python_version < '3.8'",
        "pathlib2": "python_version < '3.4' and sys_platform != 'win32'",
        "six": null,
    },
    "python": { ... }
}
```

One key in the dependency mapping is required: `dependencies`. This should be
a mapping, each key of which is also an existing key in the top-level
`dependencies` mapping, and indicates the current dependency requires these
dependencies to be installed.

Each value in this `dependencies` mapping should either be `null`, or a valid
environment marker as specified in PEP 508. A dependency specified by the key
is required if its corresponding value is `null`, or evaluates to true as an
environment marker.

Python packaging reserves one other key here: `python`, which describes how a
dependency can be satisfied by installing a Python package. Contents of this
value are discussed in a later section.


### Satisfying a dependency with a Python package

> NOTE: Keys in this section are subject to change, because I want them to
> match the ones chosen in the package metadata work. I’m lining out my own
> opinion of how these keys should be designed.

If a `python` key is present in a dependency mapping, its content should be a
mapping describing how the Python package should specified to satisfy the
dependency. There are five possible forms:

1. Local Python source
2. Editable local Python source
3. Direct URL reference
4. Indirect reference

The last two correspond to the [PEP 440] requirement variants. All forms
require one key, `name`, that specifies the name of the to-be-installed Python
distribution.

#### Local Python source

```json
{
    "python": {
        "name": "my-plugin",
        "path": "./vendor/myplugin"
    }
}
```

One key `path` is required. Its value should be a relative or absolute path
pointing to a directory containing an installable Python project. A relative
path should be resolved based on the directory containing the lock file.

Note that `path` should not point to a file. To install from an archive, use
the direct URL reference form.

#### Editable local Python source

```json
{
    "python": {
        "name": "my-plugin",
        "editable": "./vendor/myplugin"
    }
}
```

One key `editable` is required. The specification of this field is the same
as `source` in a local Python source, except the distribution is expected to
be installed as an editable installation.

> NOTE: I am intentionally excluding editable VCS URLs because YAGNI.

#### Direct URL reference

```json
{
    "python": {
        "name": "pip",
        "direct": "https://github.com/pypa/pip/archive/1.3.1.zip"
    }
}
```

One key `direct` is required, which points to a valid value specified by
[PEP 440] direct references. This can be converted to a PEP 440 direct
reference with

```python
def deserialize(dependency):
    data = dependency["python"]
    return f'{data["name"]} @ {data["direct"]}'
```

If the value to `direct` is a relative path, it should be resolved based on
the directory containing the lock file. (See [What is the correct
interpretation of path-based PEP 508 URI_reference?][508-uri-discussion].)

Note that `direct` should not point to a directory. To install from a “flat”
source directory, use the local Python source form.

#### Indirect reference

An indirect reference contains information for the installation tool to resolve
the distribution into a direct URL lazily on installation, instead of eagerly
during locking. This allows for installation tools to implement optimizations
to let the user download the “same” distribution from different sources.

```json
{
    "python": {
        "name": "django",
        "source": "pypi",
        "version": "3.0.2"
    }
}
```

Two keys in addition to `name` are required in this form. `source` references
the name of a “distribution source” to use on installation, and `version`
specifies the version of the distribution to select from the source.

### Resolving indirect references

A top-level key `sources` contains all the distribution sources available for
reference in this lock file:

```json
{
    "sources": {
        "pypi": {
            "type": "simple",
            "url": "https://pypi.org/simple"
        },
        "company": {
            "type": "find-links",
            "url": "https://example.com/packages.html"
        }
    }
}
```

Each key in `sources` is the identifier the source is referenced in
`dependencies`. All fields in the value are required. `type` denotes the type
of the source; Python packaging reserves two values `simple` and `find-links`,
corresponding to a source implementing PEP 503 Simple Repository API, and
a “find-links” page as implemented by pip.

An installer may choose to implement mechanisms to override any of the source
values, e.g. point `pypi` to `https://pypi.tuna.tsinghua.edu.cn/simple`, so any
Python distribution reference setting `"source": "pypi"` would resolve the
distribution against that mirror, instead of `https://pypi.org/simple` as
specified in the lock file.

### Distribution validation

A top-level key `validations` contains values that can be used to validate
downloaded artifacts at install time.

```json
{
    "validations": {
        "pip": [
            "sha1:da9234ee9982d4bbb3c72346a6de940a148ea686",
            "md5:cbb27a191cebc58997c4da8513863153"
        ]
    }
}
```

Each key in `validations` should reference a dependency listed in the top-level
`dependencies` mapping. The value is a sequence of validation declarations for
the artifact downloaded to satisfy the dependency. An artifact is considered
validated if *any* of the listed declarations validates. Dependencies without
a corresponding key in `validations` always pass this validation phase. They
may still implement their own validations based on other values in the lock
file.

The validation declaration format is defined by individual dependency
implementations. Python packages uses a string of form `{algorithm}:{hash}` to
declare possible hash values of the downloaded artifact. Other dependency
formats may use the format as well, or implement their own validation
protocols.


## File format

The lock file should be serialized in readable JSON format, an equivalent of
the following Python implementation:

```python
def write_lock(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4,
            sort_keys=True,
        )
```

The file name must ends with `.lock.json`.


## Example

See `pyproject.lock.json` for an example lock file populated from
`requirements.in`.


---

[PEP 440]: https://www.python.org/dev/peps/pep-0440/
[PEP 503]: https://www.python.org/dev/peps/pep-0503/
[PEP 508]: https://www.python.org/dev/peps/pep-0508/
[508-uri-discussion]: https://discuss.python.org/t/what-is-the-correct-interpretation-of-path-based-pep-508-uri-reference/2815
[docutils 0.15]: https://pypi.org/project/docutils/0.15/#files
