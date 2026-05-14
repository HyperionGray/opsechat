- All files with source code are to be kept under approximately 600-700 lines. If some module, file, concept, etc. needs to exceed that, split it up into logical modules/includes
- When i say "test" something - it means build an automated but *user realistic* test. Not just checking if something parses, not some weak automated test. The test should
  verify that when an actual user is going to perform an action it works.
- When i say "test" something - it also means to try it in an actual deployment in your environment and go through the flow as the user.
- All tests are to be reported back in comments. Lack of this will get a PR rejected outright.
- Projects should be organized and semi-standardized. Examples: a python project should look something like 

```
src/{logical_module_1,logical_module_2...} etc.
docs/         # all docs go in here except for a base README.me, QUICKSTART.md, USER_DOCS.md, DEVELOPER_DOCS.md
tests/        # all tests go in here, see above for test guidelines
scripts/      # helper scripts go in here. These should NOT be base source code, they should be helpers for common actions the user or I might need to take often
build/        # if needed, mainly for C code but use if needed for any code.
bin/          # for any binaries that are built
Makefile/<some sort of build file>    # this can be a makefile, CMake stuff, a .pf file for building
```

The above is the basic example shape of a logical project. Some projects are large, if that is the case here then those directories may be repeated several times
in intuitively named directories that make up the project. For example:

```
pfs-sdk/memhub-sdk/<structure outlined above>
pfs-sdk/other-sdk/<structure outlined above>
```

If additional directories are needed besides those above, please make or look for another directory that is intuitively named and part of an important separate
category of object that is needed.

- Keep code clean, modular, relatively small functions or objects, and logically separated. I should be able to read your code and understand what it does by
  seeing the flow, order things are written in, naming, and structure.
