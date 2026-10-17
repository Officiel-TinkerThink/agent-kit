# Architecture rules

## Layers

- The domain layer is the package `code/domain`.
- The application layer is the package `code/application`.
- The infrastructure layer is the package `code/infrastructure`.

## Dependency direction

- Domain modules import only the Python standard library and modules of the domain package.
- The domain package `__init__.py` must not re-export anything from `infrastructure`.
- Application modules may import the domain package and the infrastructure layer.
- Infrastructure modules may import the Python standard library and the domain package.
- Reviewers check every import added by a change against these rules, not only the file the import sits in.
