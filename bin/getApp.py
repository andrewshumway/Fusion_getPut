#!/usr/bin/env python3

"""
Use at your own risk.  No compatibility or maintenance or other assurance of suitability is expressed or implied.
Update or modify as needed
"""

# 4.x notes. Trying new approach.  Fetch zip and unpack various object elements.
# rather than use export/import I'll use the base APIs because they support /api/apollo/apps/[appname]/[objecttype]
# endpoints because that will (hopefully) simplify linking things together
#
# assumptions
# 1. only one app will be imported or exported at a time
# 2. signals and signals_aggr collections will be skipped
# 3. only collections in the 'default' cluster will be processed
#
# initially supported object types
# App
# collection
# pipelines
# profiles
# datasources
#
# support added for
# search clusters
# query rewrite

# Types with UNKNOWN affect
# features
# links
# objectGroups

#
# query Fusion for all datasources, index pipelines and query pipelines.  Then make lists of names
# which start with the $PREFIX so that they can all be exported.

#  Requires a python 3.x+ interpreter (tested on 3.8.9)
try:
    import json, sys, argparse, os, subprocess, sys, requests, datetime, re, shutil, types,base64
    from io import BytesIO, StringIO
    # StringIO moved into io package for Python 3
    # from StringIO import StringIO
    from zipfile import ZipFile
    from argparse import RawTextHelpFormatter

    # get current dir of this script
    cwd = os.path.dirname(os.path.realpath(sys.argv[0]))

    OBJ_TYPES = {
        "fusionApps": { "ext": "APP"}
        ,"zones":{"ext":"ZN"}
        ,"templates":{"ext":"TPL"}
        ,"dataModels":{"ext":"DM"}
        ,"indexPipelines": { "ext": "IPL" }
        ,"queryPipelines": { "ext": "QPL" }
        ,"indexProfiles": { "ext": "IPF"  }
        ,"queryProfiles": { "ext": "QPF" }
        ,"parsers": { "ext": "PS" }
        ,"dataSources": { "ext": "DS" }
        ,"collections": { "ext": "COL", "urlType":"collection"}
        ,"jobs": { "ext": "JOB" }
        ,"tasks": { "ext": 'TSK' }
        ,"sparkJobs": { "ext": 'SPRK' , "filelist": [] }
        ,"blobs": { "ext": "BLOB" ,"urlType":"blob"}
        # features can't be fetched by id in the export API but come along with the collections.
        ,"features": { "ext": "CF"}
    }

    searchClusters = {}
    collections = []
    PARAM_SIZE_LIMIT = 6400
    TAG_SUFFIX: str = "_mergeForm"

    def eprint(*args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    def sprint(msg):
        # change inputs to *args, **kwargs in python 3
        # print(*args, file=sys.stderr, **kwargs)
        print(msg)
        sys.stdout.flush()

    def debug(msg):
        if args.debug:
            sprint(msg)

    def verbose(msg):
        if args.verbose:
            sprint(msg)

    def getSuffix(type):
        return '_' + OBJ_TYPES[type]['ext'] + '.json'


    def applySuffix(f, type):
        suf = OBJ_TYPES[type]["ext"]
        if not f.endswith(suf):
            return f + getSuffix(type);
        return f + ".json"


    def initArgs():
        env = {}  # some day we may get better environment passing
        debug('initArgs start')

        # setting come from command line but if not set then pull from environment
        if args.server == None:
            args.server = initArgsFromMaps("lw_IN_URL", "https://localhost", os.environ, env)
        elif not args.server.lower().startswith("http"):
            eprint("--server argument must be in url format e.g. http://lowercase")
            sys.exit(2)

        if args.user == None:
            args.user = initArgsFromMaps("lw_USERNAME", "admin", os.environ, env)

        if args.password == None:
            args.password = initArgsFromMaps("lw_PASSWORD", "password123", os.environ, env)

        if args.app == None:
            if args.zip == None:
                sys.exit("either the --app or the --zip argument is required.  Can not proceed.")

        if args.dir is None and args.zip is None:
            # make default dir name
            defDir = str(args.app) + "_" + datetime.datetime.now().strftime('%Y%m%d_%H%M')
            args.dir = defDir
        elif args.dir is None and args.zip is not None:
            defDir = str(args.zip) + "_" + datetime.datetime.now().strftime('%Y%m%d_%H%M')
            args.dir = defDir


    def initArgsFromMaps(key, default, penv, env):
        # Python3: dict.has_key -> key in dict
        if key in penv:
            debug("penv has_key" + key + " : " + penv[key])
            return penv[key]
        else:
            # Python3: dict.has_key -> key in dict
            if key in env:
                debug("eenv has_key" + key + " : " + env[key])
                return env[key]
            else:
                debug("default setting for " + key + " : " + default)
                return default


    def makeBaseUri():
        uri = args.server + "/api"
        return uri


    def doHttp(url, usr=None, pswd=None, headers={},params={}):
        response = None
        auth = None
        if usr is None:
            usr = args.user
        if pswd is None:
            pswd = args.password

        if args.jwt is not None:
            headers["Authorization"] = f'Bearer {args.jwt}'
        else:
            auth=requests.auth.HTTPBasicAuth(usr, pswd)

        verify = not args.noVerify
        try:
            debug("calling requests.get url:" + url + " usr:" + usr + " pswd:" + pswd + " headers:" + str(headers))
            response = requests.get(url, auth=auth, headers=headers, verify=verify,params=params)
            return response
        except requests.ConnectionError as e:
            eprint(e)


    def makeExportParamsFromJson(j):
        """
        Make n export URL containing all of the needed id えぇめんts existing in the objects.json file
        :param j:
        :return　list of sized dictionaries of params such that none exceeds 6.5k:
        """
        url = makeBaseUri() + "/objects/export"
        allParams = []
        params = {"filterPolicy":"system","deep":"false"}
        #allParams.insert(0,params)

        if j is None or not "objects" in j:
            return allParams

        objects = j["objects"]
        # save the fusionApps[0] element
        if "fusionApps" in objects and isinstance(objects["fusionApps"],list):
            OBJ_TYPES["fusionApps"]["appDef"] = objects["fusionApps"][0]

        keys = OBJ_TYPES.keys()

        for key in keys:
            if key in objects:
                items = objects[key]

                itms = []
                for item in items:
                    if isinstance(item,dict) \
                            and "id" in item \
                            and not (key == "blobs" and item["id"].startswith("prefs-")):
                        itms.append(item["id"])

                if isinstance(itms, list) and "urlType" in OBJ_TYPES[key]:
                    # check and see if adding this set of params would push us over the limit.
                    # If so, store off the smaller params set in allParams and start a new one
                    if len(str(params)) + len(str(itms)) > PARAM_SIZE_LIMIT:
                        allParams.insert(0,params)
                        params = {"filterPolicy":"system","deep":"false"}
                        params[OBJ_TYPES[key]["urlType"] + ".ids"] = itms
                    # otherwise add to the current params list since we are under the size limit
                    else:
                        params[OBJ_TYPES[key]["urlType"] + ".ids"] = itms

        ## add any fragment params in to the results.  For small apps, this may be everything
        if len(params) > 1 and not params in allParams:
            allParams.insert(0,params)
        return allParams



    def doGetJsonApp():
        """
        fetch a json export of the app.  The purpose is to get a list of everything that belongs to the App.
        Then, after extracting all but the blobs and collections fetch those into Zip(s) and extract including files.
        All this to work around the fact that we can't export an app to a zip without query_rewrite
        """
        url = makeBaseUri() + "/objects/export?filterPolicy=system&app.ids=" + args.app
        headers = {'accept': 'application/json'}
        try:

            debug("calling requests.get url:" + url + " headers:" + str(headers))
            verbose(f"Getting JSON elements of APP {args.app} from {args.server}")
            response = doHttp(url,headers=headers)
            if response is not None and response.status_code == 200:
                contentType = response.headers['Content-Type']
                if "application/json" in contentType:
                    j = json.loads(response.content)
                    exportParams = makeExportParamsFromJson(j)
                    ## in addition to processing all of the zip files from exportParam sets, we need to output
                    # APP and possibly features but don't grab blobs and collections.  Those need to come from full zips
                    j['objects'].pop('blobs')
                    j['objects'].pop('collections')

                    verbose(f"Extracting contents of downloaded APP {args.app}")
                    extractAppFromZip(objects=j,validateAppName=True)
                    url = makeBaseUri() + "/objects/export"
                    index = 0
                    for params in exportParams:
                        if args.verbose:
                            index += 1
                            sprint(f"\nFetching Zip export from {url} params set {index}")
                        zipfile = doHttpZipGet( url,params=params)
                        extractAppFromZip(zipfile,validateAppName=False)

            else:
                if response is not None and response.status_code == 401 and 'unauthorized' in response.text:
                    eprint(
                        "Non OK response of " + str(response.status_code) + " for URL: " + url + "\nCheck your password\n")
                elif response is not None and response.status_code:
                    eprint("Non OK response of " + str(response.status_code) + " for URL: " + url)
        except Exception as e:
            eprint( f"Exception when fetching App: {str(e)}" )



    def doHttpZipGet(url, usr=None, pswd=None,params={}):
        response = None
        response = doHttp(url, usr, pswd,params=params)
        if response is not None and response.status_code == 200:
            contentType = response.headers['Content-Type']
            debug("contentType of response is " + contentType)
            # use a contains check since the contentType may be 'application/json; utf-8' or multi-valued
            if "application/zip" in contentType:
                content = response.content
                zipfile = ZipFile(BytesIO(content))
                return zipfile
            else:
                eprint("Non Zip content type of '" + contentType + "' for url:'" + url + "'")
        elif response is not None and response.status_code != 200:
            eprint("Non OK response of " + str(response.status_code) + " for URL: " + url)
            if response.reason is not None:
                eprint("\tReported Reason: '" + response.reason + "'")
        else:
            # Bad url?? bad protocol?
            eprint("Problem requesting URL: '" + url + "'.  Check server, protocol, port, etc.")


    def extractAppFromZip( zipfile = None, objects=None, validateAppName = True):
        """
        Either zipfile or objects must be valued but not both

        :param zipfile:
        :param objects:
        :param validateAppName: if True, the objects.fusionApps[0].id must equal args.app or an error will be printed
        :return:
        """

        if (zipfile and objects) or not (zipfile or objects):
            raise ValueError('Either zipfile or objects parameter is required.')

        filelist = []
        if zipfile:
            filelist = zipfile.namelist()
            if not "objects.json" in filelist:
                sys.exit("Exported zip does not contain objects.json.  Can not proceed.")
            jstr = zipfile.open("objects.json").read()
            objects = json.loads(jstr)

        # check to be sure that the requested application exists and give error if not
        if validateAppName and args.app is not None and not ( objects and
                                     (len(objects['objects']) > 0) and
                                     ( objects['objects']['fusionApps']) and
                                     ( objects['objects']['fusionApps'][0]['id']) and
                                     ( objects['objects']['fusionApps'][0]['id'] == args.app)):
            sys.exit("No Fusion App called '" + args.app + "' found on server '" + args.server + "'.  Can not proceed.")

        # sorting ensures that collections are known when other elements are extracted
        # python 3 iterkeys() -> keys()
        for type in sorted(objects['objects'].keys()):
            # obj will be the name of the object type just under objects i.e. objects.collections, indexPipelines etc.
            doObjectTypeSwitch(objects['objects'][type], type)

        # global collections[] will hold exported collection names.  Get the configsets for those and write them out as well
        for filename in filelist:
            if shouldExtractFile(filename):
                extractFromZip(filename, zipfile)
            elif shouldExtractEmbeddedZip(filename):
                extractZip(filename, zipfile)

        if zipfile:
           zipfile.close()


    # check for blob zips which should be extracted intact or non-zipped configsets
    def shouldExtractFile(filename):
        path = filename.split('/')
        extension = os.path.splitext(path[-1])
        file = extension[0]
        ext = extension[-1]
        if path[0] == 'blobs':
            return not file.startswith("prefs-")
        # in 4.0.2 configsets are already unzip so each file can be extracted.  this block should catch 4.0.2 case
        # and shouldExtractConfig will catch the 4.0.1 case
        elif len(path) > 2 and path[0] == 'configsets' and ext != '.zip' and path[1] in collections:
            return True
        return False


    # check for embeded and zipped configsets in need of extraction
    def shouldExtractEmbeddedZip(filename):
        path = filename.split('/')
        extension = os.path.splitext(path[-1])
        file = extension[0]
        ext = extension[-1]
        if path[0] == 'configsets' and ext == '.zip' and file in collections:
            return True
        return False


    def extractFromZip(filename, zip):
        # there seems to be a bug in the creation of the zip by the export routine and some files are zero length
        # don't save these since they would produce an empty file which would overwrite the blob on import
        if zip.getinfo(filename).file_size > 0:
            zip.extract(filename, args.dir)
        else:
            eprint("File " + filename + " in archive is zero length. Extraction skipped.")


    def extractZip(filename, zip):
        path = filename.split('/')
        path[-1] = os.path.splitext(path[-1])[0]
        outputDir = os.path.join(args.dir, *path)
        zfiledata = BytesIO(zip.read(filename))
        with ZipFile(zfiledata) as zf:
            zf.extractall(outputDir)


    #
    # do something with some json based on the type of the json array
    def doObjectTypeSwitch(elements, type):
        switcher = {
            "fusionApps": collectById
            , "collections": lambda l_elements, l_type: collectCollections(l_elements, l_type)
            , "features": lambda l_elements, l_type: collectFeatures(l_elements, l_type)
            , "indexPipelines": collectById
            , "queryPipelines": collectById
            , "indexProfiles": collectProfileById
            , "queryProfiles": collectProfileById
            , "parsers": collectById
            , "dataSources": collectById
            , "tasks": collectById
            , "jobs": collectById
            , "sparkJobs": collectById
            , "templates":  lambda l_elements, l_type: collectById(l_elements, l_type, "id","name")
            , "zones": lambda l_elements, l_type: collectById(l_elements, l_type, "id","name")
            , "dataModels": collectById
            , "blobs": lambda l_elements, l_type: collectById(l_elements, l_type, "filename","dir")

        }
        # get the function matchng the type or a noop
        processTypedElementFunc = switcher.get(type, lambda *args: None)
        # call the function passing elements and type
        processTypedElementFunc(elements, type)


    # Recurse through the entire JSON tree and sort all key/values
    def sortedDeep(d):
        def makeTuple(v): return (*v,) if isinstance(v,(list,dict)) else (v,)
        if isinstance(d,list):
            return sorted( map(sortedDeep,d) ,key=makeTuple )
        if isinstance(d,dict):
            return { k: sortedDeep(d[k]) for k in sorted(d)}
        return d

    def jsonToFile(jData, type,filename, altSubDir=None):
        jData = sortedDeep(jData)
        # replace spaces in filename to make the files sed friendly
        filename2 = filename.replace(' ', '_')
        if altSubDir is None:
            subDir = type
        else:
            subDir = altSubDir

        if type and not os.path.isdir(os.path.join(args.dir,subDir)):
            os.makedirs(os.path.join(args.dir,subDir))


        with open(os.path.join(args.dir, subDir,filename2), 'w') as outfile:
            # sorting keys makes the output source-control friendly.  Do we also want to strip out
            if "updates" in jData:
                jData.pop('updates', None)
            if "modifiedTime" in jData:
                jData.pop('modifiedTime', None)
            if "version" in jData:
                jData.pop('version', None)

            if not args.noStageIdMunge and "stages" in jData:
                stages = jData["stages"]
                for i, stage in enumerate(stages):
                    if "secretSourceStageId" in stage:
                        stage.pop("secretSourceStageId",None)
                    stage["id"] = mungeStageId(stage, str(i))

            outfile.write(json.dumps(jData, indent=4, sort_keys=True,separators=(', ', ': ')))
            outfile.close()

    def mungeStageId(stage, idxStr):
        type = stage.get("type","")
        label = stage.get("label","")
        return re.sub("[ -]","_",type + ":" + label + ":" + idxStr)

    def makeScriptReadable(element: object, tag: str) :
        if tag in element:
            script = element[tag]
            ##update element with split script
            element[tag + TAG_SUFFIX] = script.splitlines()


    def makeDiffFriendly(e, type):
        xformTags = [
            "script" # scala script, python
            ,"transformScala" # PBL
            ,"transformSQL" # PBL
            ,"sql" # sqlTemplate
            ,"sparkSQL" # sqlTemplate, headTail, tokenPhraseSpellCorrection
            ,"misspellingSQL" # synonym detection
            ,"phraseSQL" # synonym detection
            ,"rollupSql" # sql_template
            #,"analyzerConfigQuery" # candidate json from some 4 sisters
            #,"notes" # candidate for multi-line descript/notes field
        ]

        if isinstance(e, dict) and type.endswith("Pipelines") and ('stages' in e.keys()):
            for stage in e['stages']:
                if isinstance(stage, dict) and ('script' in stage.keys()):
                    stgKeys = stage.keys()
                    if 'script' in stgKeys:
                        makeScriptReadable(stage,"script")
                    if 'condition' in stgKeys and '\n' in stage['condition']:
                        makeScriptReadable(stage,"condition")
        elif isinstance(e,dict) and type == "sparkJobs":
            for tag in xformTags:
                if tag in e:
                    makeScriptReadable(e,tag)

    def collectById(elements, type, keyField='id', nameSpaceField=None):
        for e in elements:
            if keyField not in e and "resource" in e:
                keyField = "resource"
            id = e[keyField]
            if type == "blobs" and id.startswith("prefs-"):
                continue
            verbose("Processing '" + type + "' object: " + id)
            # spin thru e and look for 'stages' with 'script'
            makeDiffFriendly(e,type)

            # some jobs have : in the id, some blobs have a path.  Remove problem characters in filename
            if nameSpaceField is not None and nameSpaceField in e:
                ns = e[nameSpaceField]
                if ns is not None:
                   ns = re.sub(r"^[/\\:\s]",'',ns)
                   filename = applySuffix( re.sub(r"[/\\:.\s]",'_',ns) + '_' + id.replace(':', '_').replace('/', '_'),type)
            else:
                filename = applySuffix(id.replace(':', '_').replace('/', '_'), type)
            jsonToFile(e,type,filename)

    def collectProfileById(elements, type):
        # this code is tentative.  The pipeline elements contains a sub object called 'ALL' which then contains the list we want
        #  update: looks like 4.1 gets rid of the ALL
        mylist = []
        if isinstance(elements, dict) and ('ALL' in elements.keys()):
            mylist = elements['ALL']
        # 4.0.0 seems to give a dict of items id:[{id:val...}]
        elif isinstance(elements, dict):
            mylist = []
            for k in elements:
                v = elements[k]
                if isinstance(v, dict):
                    mylist.append(v)
                elif isinstance(v, list):
                    mylist.extend(v)
        elif isinstance(elements, list):
            mylist = elements
        if mylist is not None:
            collectById(mylist, type)
        elif len(elements) > 1:
            eprint("Unknown JSON structure encountered.  Profiles subtree should be 'ALL' element or array of Profiles.")


    def collectFeatures(elements,type="features"):
        for col in elements:
            features = elements[col]
            filename = applySuffix(col.replace(':', '_').replace('/', '_'), type)
            jsonToFile(features,type,filename,altSubDir="collectionFeatures")

    def collectCollections(elements, type="collections"):
        keep = []
        for e in elements:
            id = e['id']
            keep.append(e)
            # make sure associated clusters are exported
            # keep track of the default collections (global) we are exporting so that schema can be exported as well
            # do not export schema for collections on non-default clusters.  Best to not mess with remote config
            if e['searchClusterId'] == 'default':
                collections.append(id)

        collectById(keep, type)


    def collectIndexPipelines(elements):
        collectById(elements, "indexPipelines")


    def main():
        initArgs()
        # create if missing
        if not os.path.isdir(args.dir):
            os.makedirs(args.dir)
        # Fetch solr clusters map so we can export if needed
        target = args.app
        zipfile = None
        if args.zip is not None:
            sprint("Getting export zip from file '" + args.zip + "'.")
            zipfile = ZipFile(args.zip, 'r')
            extractAppFromZip(zipfile)
        else:
            doGetJsonApp()


    if __name__ == "__main__":
        scriptName = os.path.basename(__file__)
        # sample line: 'usage: getProject.py [-h] [-l] [--protocol PROTOCOL] [-s SERVER] [--port PORT]'
        description = ('______________________________________________________________________________\n'
                       'Get artifacts associated with a Fusion app and store them together in a folder \n'
                       'as subfolders, and flat files. These files can be stored, manipulate and uploaded, \n'
                       'to a Fusion instance as needed. NOTE: if launching from getApp.sh, \n'
                       'defaults will be pulled from the bash environment plus values from bin/lw.env.sh\n'
                       '______________________________________________________________________________'
                       )
        parser = argparse.ArgumentParser(description=description, formatter_class=RawTextHelpFormatter)

        # parser.add_argument_group('bla bla bla instruction go here and they are really long \t and \n have tabs and\n newlines')
        parser.add_argument("-a", "--app", help="App to export")  # ,default="lwes_"
        parser.add_argument("-d", "--dir",
                            help="Output directory, default: '${app}_ccyymmddhhmm'.")  # ,default="default"
        parser.add_argument("-s", "--server", metavar="SVR",
                            help="Server url e.g. http://localhost:80, \ndefault: ${lw_OUT_URL}.")  # default="http://localhost:8764"
        parser.add_argument("-u", "--user",
                        help="Fusion user name, default: ${lw_USER}.")  # ,default="admin"
        parser.add_argument("--password",
                        help="Fusion Password,  default: ${lw_PASSWORD}.")  # ,default="password123"
        parser.add_argument("--jwt",help="JWT token for access to Fusion.  If set, --user and --password will be ignored",default=None)
        parser.add_argument("-v", "--verbose", help="Print details, default: False.", default=False,
                            action="store_true")  # default=False
        parser.add_argument("--debug", help="Print debug messages while running, default: False.", default=False,
                            action="store_true")  # default=False
        parser.add_argument("--noVerify", help="Do not verify SSL certificates if using https, default: False.",
                            default=False, action="store_true")  # default=False

        parser.add_argument("-z", "--zip",
                            help="Path and name of the Zip file to read from rather than using an export from --server, \ndefault: None.",
                            default=None)
        parser.add_argument( "--noStageIdMunge", help="Experimental: may become default.  If True, do not munge pipeline stage ids. default: False.", default=False,
                             action="store_true")


                            # print("args: " + str(sys.argv))
        args = parser.parse_args()

        main()
except ImportError as ie:
    print("Failed to Import from module: ",
          ie.name,
          "\ninstall the module via the pip installer\n\nExample:\npip3 install ",
          ie.name, file=sys.stderr)
except Exception as e:
    msg = None
    if hasattr(e,"msg"):
        msg = e.msg
    elif hasattr(e,'text'):
        msg = e["text"]
    else:
        msg = str(e)
    print("Exception: " + msg, file=sys.stderr)
