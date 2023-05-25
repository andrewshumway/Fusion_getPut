# Overview

Utilities for getting or putting a 5.x Fusion App, unpacking and manipulating the output elements, and PUTting the elements 
back to the same or different Fusion instance.

## This version of getPut (in the V2.0.x branch) does not set the `/apollo/` path on Fusion urls and so is not compatible 
with older Fusion 4 versions.  If you want Fusion 3 or 4 compatibility, use the version in the [v.1.0.x branch](https://github.com/andrewshumway/Fusion_getPut/tree/v1.0.x).

Version 2.0.x makes several changes from the original GetPut utilities
* Utilities intended for support of Fusion 3.x are removed.  This includes get/put Project and renameProject
* Utilities which work well enough in 3, 4, or 5.x, but are not related to app import/export are **removed icluding**:
  * replaceTokens
  * copyPipeiine
  * countdiff
  * getBlob
  * export/import of query_rewrite rules (mostly because it is slow, rarely used, and the APIs are problematic)
* input parameters are simplified.  This includes:
   * unifying the various protocol, port, server parameters into a single URL param
   * removing some parameters which only exist for legacy 4.x support.
   * removing some parameters that only exist to support a small i.e. 10% use-case
  
The original GetPut utilities were primarily designed for PS people who want to look at, extract, manipulate, share or otherwise get at the Fusion objects that make up a Project.
Over time, other needs have surfaced:
* explode the App export zip to  individual files for:
  * manipulation
  * search to answer questions like "what else uses this thing" 
  * back up to source control
* see scripts in a diff-friendly format

This version will focus more on the newer use cases while assuming that other utilities can/will:
* filter out unwanted files 
* jsonPath based search/replace transformations 

##  Import or Export Fusion Apps

Use `getApp.sh` to export a Fusion App and store it as files in an output directory.
```markdown
usage: getApp.py [-h] [-a APP] [-d DIR] [-s SVR] [-u USER]
                 [--password PASSWORD] [--jwt JWT] [--apiKey APIKEY] [-v]
                 [--debug] [--noVerify] [-z ZIP] [--noStageIdMunge]

______________________________________________________________________________
Get artifacts associated with a Fusion APP and store them as flat files in a 
folder and subfolders.  These files can be stored, manipulate and uploaded, 
to a Fusion instance as needed. NOTE: if launching from getApp.sh, 
defaults will be pulled from the bash environment plus values from bin/lw.env.sh
______________________________________________________________________________

optional arguments:
  -h, --help            show this help message and exit
  -a APP, --app APP     App to export
  -d DIR, --dir DIR     Output directory, default: '${app}_ccyymmddhhmm'.
  -s SVR, --server SVR  Server url e.g. http://localhost:80, 
                        default: ${lw_OUT_URL}.
  -u USER, --user USER  Fusion user name, default: ${lw_USER}.
  --password PASSWORD   Fusion Password,  default: ${lw_PASSWORD}.
  --jwt JWT             JWT token for access to Fusion.  If set, --user, --password will be ignored
  --apiKey APIKEY       API Key for access to Fusion.  If set, --user, --password and --jwt will be ignored
  -v, --verbose         Print details, default: False.
  --debug               Print debug messages while running, default: False.
  --noVerify            Do not verify SSL certificates if using https, default: False.
  -z ZIP, --zip ZIP     Path and name of the Zip file to read from rather than using an export from --server, 
                        default: None.
  --noStageIdMunge      Experimental: may become default.  If True, do not munge pipeline stage ids. default: False.
```
Use `putApp` to import a Fusion App from files in an input directory.

```markdown
usage: putApp.py [-h] -d DIR [--failOnStdError] [-s SVR] [-u USER]
                 [--password PASSWORD] [--jwt JWT] [--apiKey APIKEY] [--debug]
                 [--noVerify] [-v] [--varFile VARFILE]

___________________________________________________________________________________
Take a folder containing .json files or directories of .json files, such as that  
produced by getApp.py, and POST the contents to a running Fusion instance.  
Existing Fusion objects will be overwritten as needed but existing Solr collections
will not be recreted.
___________________________________________________________________________________

optional arguments:
  -h, --help            show this help message and exit
  -d DIR, --dir DIR     Input directory (with a *_APP.json file), required.
  --failOnStdError      Exit the program if StdErr is written to i.e. fail when any call fails.
  -s SVR, --server SVR  Fusion server to send data to. Default: ${lw_OUT_URL} or 'localhost'.
  -u USER, --user USER  Fusion user, default: ${lw_USER} or 'admin'.
  --password PASSWORD   Fusion password,  default: ${lw_PASSWORD} or 'password123'.
  --jwt JWT             JWT token for access to Fusion.  If set, --user, --password will be ignored
  --apiKey APIKEY       API Key for access to Fusion.  If set, --user, --password and --jwt will be ignored
  --debug               Print debug messages while running, default: False.
  --noVerify            Do not verify SSL certificates if using https, default: False.
  -v, --verbose         Print details, default: False.
  --varFile VARFILE     Protected variables file used for password replacement (if needed) default: None.
~~~~```

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
