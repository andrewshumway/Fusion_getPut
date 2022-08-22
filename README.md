# Overview

Utilities for getting or putting a 5.x Fusion App, manipulating the output eleents, and PUTting the elements 
back to Fusion (not necessarily the same source and target instances).

##This version of getPut (in the V2.0.x branch) does not fully support Fusion 4.x.If you want Fusion 3/4 support, use the version in the [Main branch](https://github.com/andrewshumway/Fusion_getPut/tree/main).

Version 2.0.x makes several changes from the original GetPut utilities
* Utilities intended for support of Fusion 3.x are removed.  This includes get/put Project and renameProject
* Utilities which work well enough in 3, 4, or 5.x, but are not related to app import/export are not included
  * replaceTokens
  * copyPipeiine
  * countdiff
  * getBlob
  * export/import of query_rewrite rules (mostly because it is slow, rarely used, and the APIs are problematic)
* input parameters are simplified.  This includes:
   * unifying the various protocol, port, server parameters into a single URL param
   * removing some parameters which only exist for legacy 4.x support.
   * removing some parameters that only exist to support a small e.g. 10% use-case
  
The original GetPut utilities were designed with a primary use case being PS people who want to look at, extract, manipulate, share or otherwise get at the Fusion objects that make up a Project.
Over time, other needs have surfaced
* explode the App export zip to  individual files for:
  * manipulation
  * search to answer questions like "what else uses this thing" 
  * back up to source control
* see scripts in a diff-friendly format

This version will focus more on these use cases while assuming that other utilities can/will:
* filter out unwanted files 
* jsonPath based search/replace transformations 

##  Import or Export Fusion Apps

Use `getApp.sh` to export a Fusion App and store it as files in an output directory.
```markdown
usage: getApp.py [-h] [-a APP] [-d DIR] [-s SVR] [-u USER]
[--password PASSWORD] [--jwt JWT] [-v] [--debug] [--noVerify]
[-z ZIP] [--noStageIdMunge]

______________________________________________________________________________
Get artifacts associated with a Fusion app and store them together in a folder
as flat files, .json, and .zip files. These can later be pushed back into the same,
or different, Fusion instance as needed. NOTE: if launching from getApp.sh,
defaults will be pulled from the bash environment plus values from bin/lw.env.sh
______________________________________________________________________________

optional arguments:
-h, --help            show this help message and exit
-a APP, --app APP     App to export
-d DIR, --dir DIR     Output directory, default: '${app}_ccyymmddhhmm'.
-s SVR, --server SVR  Server url e.g. http://localhost:80,
default: ${lw_IN_SERVER} or 'localhost'.
-u USER, --user USER  Fusion user name, default: ${lw_USER} or 'admin'.
--password PASSWORD   Fusion Password,  default: ${lw_PASSWORD} or 'password123'.
--jwt JWT             JWT token for access to Fusion.  If set, --user and --password will be ignored
-v, --verbose         Print details, default: False.
--debug               Print debug messages while running, default: False.
--noVerify            Do not verify SSL certificates if using https, default: False.
-z ZIP, --zip ZIP     Path and name of the Zip file to read from rather than using an export from --server,
default: None.
--noStageIdMunge      Experimental: may become default.  If True, do not munge pipeline stage ids. default: False.
```
Use `putApp` to import a Fusion App from files in an input directory.

```markdown
usage: getApp.py [-h] [-a APP] [-d DIR] [-s SVR] [-u USER]
                 [--password PASSWORD] [--jwt JWT] [-v] [--debug] [--noVerify]
                 [-z ZIP] [--noStageIdMunge]

______________________________________________________________________________
Get artifacts associated with a Fusion app and store them together in a folder 
as subfolders, and flat files. These files can be stored, manipulate and uploaded, 
to a Fusion instance as needed. NOTE: if launching from getApp.sh, 
defaults will be pulled from the bash environment plus values from bin/lw.env.sh
______________________________________________________________________________

optional arguments:
  -h, --help            show this help message and exit
  -a APP, --app APP     App to export
  -d DIR, --dir DIR     Output directory, default: '${app}_ccyymmddhhmm'.
  -s SVR, --server SVR  Server url e.g. http://localhost:80, 
                        default: ${lw_IN_SERVER} or 'localhost'.
  -u USER, --user USER  Fusion user name, default: ${lw_USER} or 'admin'.
  --password PASSWORD   Fusion Password,  default: ${lw_PASSWORD} or 'password123'.
  --jwt JWT             JWT token for access to Fusion.  If set, --user and --password will be ignored
  -v, --verbose         Print details, default: False.
  --debug               Print debug messages while running, default: False.
  --noVerify            Do not verify SSL certificates if using https, default: False.
  -z ZIP, --zip ZIP     Path and name of the Zip file to read from rather than using an export from --server, 
                        default: None.
  --noStageIdMunge      Experimental: may become default.  If True, do not munge pipeline stage ids. default: False.
```

##### Environment variables from `bin/lw.env.sh` file

Several variable defaults are contained in the 'lw.env.sh' script. Most of the bash scripts in Quickstart invoke this to set these defaults in the local environment.  
To override, either edit your copy of the script or `export KEY=VALUE` in the parent bash environment.  
 3. lw_OUT_SERVER - the server name or IP used for exporting (default https://localhost)
 4. lw_IN_SERVER - the server name or IP used for importing (default https://localhost) 
 6. lw_USERNAME - the name of the fusion user performing operations (default admin)
 7. lw_PASSWORD - the password of the fusion user performing operations (default password123)
 

### Installation Notes:

* While these utilities use Python 3.15+ and should be usable on any platform with a Python interpreter, the development platform is the BSD unix flavor common on Macintosh computers.
* The Python interpreter will need to have packages installed.  This can be done via `pip` or other python package management tools
  * `requests`
