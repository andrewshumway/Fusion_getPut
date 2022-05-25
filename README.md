# Overview

Utilities for getting or putting a 5.x Fusion App, manipulating the output eleents, and PUTting the elements 
back to Fusion (not nessisarily the same source and target instances).

Version 2.0.x makes several changes from the original GetPut utilities
* Utilities intended for support of Fusion 3.x are removed.  This includes get/put Project and renameProject
* Utilities which work well enough in 3, 4, or 5.x, but are not related to app import/export are not included
  * replaceTokens
  * copyPipeiine
  * countdiff
  * getBlob
  * export/import of query_rewrite rules (mostly because it is slow, rarely used, and the APIs are problematic)
* input parameters are simplified.  This includes unifying the various protocol, port, server parameters into a single URL param as well as removing some parameters which only exist for legacy 4.x support.

The original GetPut utilities were designed with a primary use case being PS people who want to look at, extract, manipulate, share or otherwise get at the Fusion objects that make up a Project.
Over time, other needs have surfaced
* back up to source control
* transform for migration to another tier i.e. dev, tst, prod

This version will focus more on these use cases and add additional features intended to ease packaging and migration tasks:
* output file filtering
* jsonPath based search/replace transformations

##  Import or Export Fusion Apps

Use `getApp.sh` to export a Fusion App and store it as files in an output directory.
```markdown

```
Use `putApp` to import a Fusion App from files in an input directory.

```markdown

```

##### Environment variables from `bin/lw.env.sh` file

Several variable defaults are contained in the 'lw.env.sh' script. Most of the bash scripts in Quickstart invoke this to set these defaults in the local environment.  
To override, either edit your copy of the script or `export KEY=VALUE` in the parent bash environment.  
 1. lw_PREFIX - (for Fusion 3.x i.e. `getProject` and `putProject` only) A prefix value used to identify collections, and pipelines which constitute a project.  
 All fusion objects belonging to the same project need to start with this value or else `getProject.sh` will not be 
 able to find them.
 2. lw_PROTOCOL - http (default) or https
 3. lw_OUT_SERVER - the server name or IP used for exporting (default localhost)
 4. lw_IN_SERVER - the server name or IP used for importing (default localhost) 
 5. lw_PORT - the fusion port i.e. 8764
 6. lw_USERNAME - the name of the fusion user performing operations (default admin)
 7. lw_PASSWORD - the password of the fusion user performing operations (default password123)
 

### Installation Notes:

* While these utilities use Python 3.15+ and should be usable on any platform with a Python interpreter, the development platform is the BSD unix flavor common on Macintosh computers.
* The Python interpreter will need to have packages installed.  This can be done via `pip` or other python package management tools
  * `requests`
