#!/usr/bin/env python3
"""
Use at your own risk.  No compatibility or maintenance or other assurance of suitability is expressed or implied.
Update or modify as needed
"""

#
# query Fusion for all datasources, index pipelines and query pipelines.  Then make lists of names
# which start with the $PREFIX so that they can all be exported.

#  Requires a python 2.7.5+ interpreter
try:
    import json, sys, argparse, os, subprocess, sys, requests, datetime, re, urllib
    from argparse import RawTextHelpFormatter
    from pathlib import Path

    # get current dir of this script
    cwd = os.path.dirname(os.path.realpath(sys.argv[0]))

    appName = None

    fusionVersion = '4.0.0'

    # this still leaves features, objectGroups, links ignored from the the objects.json export
    OBJ_TYPES = {
        "fusionApps": { "ext": "APP"  , "filelist": [] }
        ,"zones":{"ext":"ZN", "filelist":[],  "api":"templating/zones","linkType":"zone"}
        ,"templates":{"ext":"TPL", "filelist":[], "api":"templating/templates","linkType":"template"}
        ,"dataModels":{"ext":"DM", "api":"data-models", "filelist":[],"linkType": "data-model"}
        ,"indexPipelines": { "ext": "IPL" , "filelist": [],"api":"index-pipelines","linkType": "index-pipeline" }
        ,"queryPipelines": { "ext": "QPL" , "filelist": [] ,"api":"query-pipelines","linkType": "query-pipeline" }
        ,"indexProfiles": { "ext": "IPF" , "filelist": [],"api":"index-profiles","linkType": "index-profile" }
        ,"queryProfiles": { "ext": "QPF" , "filelist": [],"api":"query-profiles","linkType": "query-profile" }
        ,"parsers": { "ext": "PS" , "filelist": [],"linkType": "parser" }
        ,"dataSources": { "ext": "DS" , "api": "connectors/datasources","filelist": [], "substitute": True,"linkType": "datasource"}
        ,"collections": { "ext": "COL" , "filelist": [] ,"linkType": "collection"}
        ,"jobs": { "ext": "JOB" , "filelist": [] }
        ,"tasks": { "ext": 'TSK' , "filelist": [],"linkType": "task" }
        ,"sparkJobs": { "ext": 'SPRK' , "filelist": [],"api":"spark/configurations" ,"linkType": "spark"}
        ,"blobs": { "ext": "BLOB" , "filelist": [] ,"linkType": "blob"}
        ,"features": { "ext": "CF" , "filelist": [] }

    }

    varReplacements = None
    replacePattern = r"^\$\{(.*)\}$"
    # array of ext =  [ OBJ_TYPES[k]['ext'] for k in OBJ_TYPES.keys() ] or [v['ext'] for v in OBJ_TYPES.values() if 'ext' in v]
    # rework above to be keyed by extension v[1]['ext'] contining value of {type, filelist}
    EXT_FILES_MAP = dict((v[1]['ext'],{'type':v[0],'filelist':v[1]['filelist']}) for v in [v for v in OBJ_TYPES.items() ])
    TAG_SUFFIX: str = "_mergeForm"

    def getSuffix(type):
        if type in OBJ_TYPES:
            return '_' + OBJ_TYPES[type]['ext'] + '.json'
        else:
            eprint("ERROR: No object Suffix of '" + type + "' is registered in OBJ_TYPES. ")

    def isSubstitutionType(type):
        if type in OBJ_TYPES and 'substitute' in OBJ_TYPES[type] and OBJ_TYPES[type]:
            return True
        return False
    def getFileListForType(type):
        if type in OBJ_TYPES:
            return OBJ_TYPES[type]['filelist']
        else:
            eprint("ERROR: No object Suffix of '" + type + "' is registered in OBJ_TYPES. ")

    def getApiForType(type):
        api = None
        if type in OBJ_TYPES:
            typeObj = OBJ_TYPES[type]
            api = type # default api the same name as type
            if 'api' in typeObj:
                api = typeObj['api']
        else:
                eprint("ERROR: No api path registered for OBJ_TYPE[ '" + type + "' ]. ")
        return api

    # lookup the type of object based on the _SUFFIX.json SUFFIX from a file
    def inferTypeFromFile(filename):
        type = None
        path = filename.split('/')
        extension = os.path.splitext(path[-1])
        file = extension[0]
        ext = extension[-1]

        underLoc = file.rfind('_')
        if underLoc > 0 and underLoc < len(file):
            tExt = file[underLoc + 1 :]
            if tExt in EXT_FILES_MAP:
                type = EXT_FILES_MAP[tExt]['type']
        return type

    # called when the OBJ_TYPES element for a given type uses a version specific api i.e. when needed api is different for 4.0.1 vs 4.0.2
    # typeObj will contain the OBJ_TYPES element for the given type and typObj must contain a versionedApi element.  Depending on the
    # version of the target Fusion machine, an api will be selected.  In the target version is not listed the default will be returned;
    def getVersionedApi(type, typeObj, default):
        api = default
        vapi = typeObj['versionedApi']
        if fusionVersion in vapi:
            api = vapi[fusionVersion]
        elif 'default' in vapi:
            api = vapi['default']
        return api

    def initArgs():
        global varReplacements
        debug('initArgs top')
        env = {} #some day we may get better environment passing

        #setting come from command line but if not set then pull from environment
        if args.server == None:
            args.server = initArgsFromMaps("lw_OUT_SERVER","localhost",os.environ,env)

        if args.user == None:
            args.user = initArgsFromMaps("lw_USERNAME","admin",os.environ,env)

        if args.password == None:
            args.password = initArgsFromMaps("lw_PASSWORD","password123",os.environ,env)

        if not os.path.isdir(args.dir):
            sys.exit( "Can not find or access the " + args.dir + " directory. Process aborted. ")

        if args.varFile != None:
            if os.path.isfile(args.varFile):
                with open(args.varFile, 'r') as jfile:
                    try:
                        varReplacements = json.load(jfile)
                    except Exception as  e:
                      sprint(f"Problem parsing json from {args.varFile}, {str(e)}")
            else:
                sys.exit( "Cannot find or access the " + args.varFile + " file.  Process aborted.")

    def initArgsFromMaps(key, default, penv,env):
        if key in penv:
            debug("penv has_key" + key + " : " + penv[key])
            return penv[key]
        else:
            if key in env:
                debug("env has_key" + key + " : " + env[key])
                return env[key]
            else:
                debug("default setting for " + key + " : " + default)
                return default

    # if we are exporting an app then use the /apps/appname bas uri so that exported elements will be linked to the app
    def makeBaseUri(forceLegacy=False):
        base = args.server + "/api"

        if not appName or forceLegacy:
            uri = base
        else:
            uri = base + "/apps/" + appName
        return uri

    def getDefOrVal(val,default):
        if val==None:
            return default
        return val
    def substituteVariable(obj, objName, varMap):
        if varMap and isinstance(obj, str) and re.search(replacePattern, obj):
            match = re.search(replacePattern, obj)
            group = match.group(1)
            if group in varMap:
                var = varMap[group]
                if var:
                    if args.verbose:
                        sprint("Substituting value in object " + objName + " for key: " + group)
                    obj = var
            else:
                eprint(f"Var replacement for file {objName} failed. Could not extract {group} from object element ")
        return obj

    def traverseAndReplace(obj, objName, varMap = None, path=None):
        # short circuit if we have no mappings
        if isinstance(varMap, dict):
            if path is None:
                path = []

            if isinstance(obj, dict):
                value = {k: traverseAndReplace(v, objName, varMap, path + [k])
                         for k, v in obj.items()}
            elif isinstance(obj, list):
                value = [traverseAndReplace(elem, objName, varMap, path + [[]])
                         for elem in obj]
            else:
                #search and see if our path is a ${var} match and if so replace with value from varFile
                value = substituteVariable(obj, objName, varMap)
        else:
            value = obj;

        return value

    def doHttpPostPut(url,dataFile, isPut,headers=None, usr=None, pswd=None):
        usr = getDefOrVal(usr,args.user)
        pswd = getDefOrVal(pswd,args.password)
        extension = os.path.splitext(dataFile)[1]
        auth = None
        if headers is None:
            headers = {}
            if extension == '.xml' or dataFile.endswith('managed-schema'):
                headers['Content-Type']="application/xml"
            elif extension == '.json':
                headers['Content-Type'] = "application/json"
            else:
                headers['Content-Type'] = "text/plain"
        if args.jwt is not None:
            headers["Authorization"] = f'Bearer {args.jwt}'
        else:
            auth=requests.auth.HTTPBasicAuth(usr, pswd)


        files = None
        try:
            if os.path.isfile(dataFile):
                with open(dataFile,'rb') as payload:
                    if isPut:
                        response = requests.put(url, auth=auth,headers=headers, data=payload,verify=isVerify())
                    else:
                        response = requests.post(url, auth=auth,headers=headers, data=payload,verify=isVerify())

                    return response
            else:
                eprint("File '" + dataFile + "' does not exist.  PUT/POST not performed.")
        except requests.ConnectionError as e:
            eprint(e)

    #  POST the given payload to apiUrl.  If it already exists then tack on the id to the URL and try a PUT
    def doPostByIdThenPut(apiUrl, payload, type, putParams='?_cookie=false', postParams='?_cookie=false',idField='id', usr=None, pswd=None, existsChecker=None):
        if existsChecker == None:
            existsChecker = lambda response,payload: response.status_code == 409

        id = payload[idField]

        if args.verbose:
            sprint("\nAttempting POST of " + type + " definition for '" + id + "' to Fusion.")
        usr = getDefOrVal(usr,args.user)
        pswd = getDefOrVal(pswd,args.password)

        auth = None
        headers = {'Content-Type': "application/json"}
        if args.jwt is not None:
            headers["Authorization"] = f'Bearer {args.jwt}'
        else:
            auth = requests.auth.HTTPBasicAuth(usr, pswd)

        url = apiUrl
        if postParams is not None:
            url += "?" + postParams
        response = requests.post(url, auth=auth,headers=headers, data=json.dumps(payload),verify=isVerify())
        url = apiUrl
        if existsChecker(response,payload):
            if args.verbose:
                sprint("The " + type + " definition for '" + id + "' exists.  Attempting PUT.")

            url = apiUrl + "/" + id
            if putParams is not None:
                url += "?" + putParams

            # if we got here then we tried posting but that didn't work so now we will try a PUT
            response = requests.put(url, auth=auth,headers=headers, data=json.dumps(payload),verify=isVerify())
            # if the PUT says the object exists, then the the likely problem is that  the object isn't linked to the current app
            # check and see if the response complains of the "id not in app" and add a link if needed.
            if (f"{id} not in app" in response.text
                     or re.search(f"The (Task|Collection|Data Model) with id '{id}' does not exist",response.text) ):
                lresponse = makeLink(type,id)
                if lresponse.status_code >= 200 and lresponse.status_code <= 250:
                    #try update again after link is in place
                    response = requests.put(url, auth=auth,headers=headers, data=json.dumps(payload),verify=isVerify())

        if response.status_code >= 200 and response.status_code <= 250:
            sprint( "Element " + type + " id: " + id + " PUT/POSTed successfully")
        elif response.status_code:
            eprint("Non OK response of " + str(response.status_code) + " when doing PUT/POST to: " + apiUrl + '/' + id + ' response.text: ' + response.text)

        return response


    def putBlobs():

        blobdir = os.path.join(args.dir,"blobs")
        for f in getFileListForType("blobs"):
            resourceType = None
            path = None
            contentType = None
            blobId = None

            # read in json and figure out path and resourceType
            with open(os.path.join(args.dir,f), 'r') as jfile:
                blobj = json.load(jfile)
                resourceType = None
                blobId = blobj['id']
                meta = blobj["metadata"]
                if meta:
                    if 'resourceType' in meta:
                        resourceType = meta['resourceType']
                    elif 'type' in meta:
                        resourceType = meta['type']

                contentType = blobj["contentType"]
                path = blobj["path"]

            url = makeBaseUri(True) + "/blobs" + path;
            if resourceType:
                url += "?resourceType=" + resourceType

            headers = {};
            if contentType:
                headers['Content-Type'] = contentType

            # convert unix path from json to os path which may be windows
            fullpath = blobdir + path.replace('/',os.sep)
            # now PUT blob
            if args.verbose:
                sprint("Uploading blob " + f)

            response = doHttpPostPut(url,fullpath, True,headers )
            if response is not None and response.status_code >= 200 and response.status_code <= 250:
                if args.verbose:
                    sprint("Uploaded " + path + " payload successfully")
                # makeBaseUri(True) is used for Fusion 4.0.1 compatibility but this requires us to make the link
                makeLink("blobs",blobId)

            elif response is not None and response.status_code:
                eprint("Non OK response: " + str(response.status_code) + " when processing " + f)

    def makeLink(resourcetype, id):
        type = None
        auth = None
        headers = {"Content-Type": "application/json"}
        if args.jwt is not None:
            headers["Authorization"] = f'Bearer {args.jwt}'
        else:
            auth = requests.auth.HTTPBasicAuth(args.user, args.password)

        if resourcetype in OBJ_TYPES and 'linkType' in OBJ_TYPES[resourcetype]:
          type = OBJ_TYPES[resourcetype]['linkType']
        else:
          type = resourcetype

        lurl = makeBaseUri(True) + "/links"
        # {"subject":"blob:lucid.googledrive-4.0.1.zip","object":"app:EnterpriseSearch","linkType":"inContextOf"}
        payload = {"subject":"","object":"","linkType":"inContextOf"}
        payload['subject'] = f"{type}:{id}"
        payload['object'] = f'app:{appName}'
        lresponse = requests.put(lurl, auth=auth,headers=headers, data=json.dumps(payload),verify=isVerify())
        if lresponse and lresponse.status_code < 200 or lresponse.status_code > 250:
            eprint("Non OK response: {}   when linking object {} to App {}".format(str(lresponse.status_code),payload['subject'],appName))

        return lresponse


    def putApps():
        global appName
        appFiles = getFileListForType("fusionApps")
        #check and make sure we have no more than one app
        if len(appFiles) == 1 :
            # put the the name of the app in a global
            f = appFiles[0]
            with open(os.path.join(args.dir,f), 'r') as jfile:
                #Capture the id in the global so that /apps/APP_ID type urls can be used to maintain APP links
                payload = json.load(jfile);
                appName = payload['id']

        else:
            sys.exit("Exactly one file with name ending in " + getSuffix("fusionApps") + " in directory " + args.dir + " is required! Exiting.")


        # GET from /api/apollo/apps/NAME to check for existence
        # POST to /api/apollo/apps?relatedObjects=false to write

        for f in appFiles:
            appsURL = args.server + "/api"
            appsURL += "/apps"
            postUrl = appsURL + "?relatedObjects=false"
            putUrl = appsURL + "/" + appName + "?relatedObjects=false"

            response = doHttp(putUrl)
            isPut = response and response.status_code == 200;
            url = putUrl if isPut else postUrl

            response = doHttpPostPut(url, os.path.join(args.dir,f), isPut)

            if response.status_code == 200:
                if args.verbose:
                    sprint( "Created App " + appName)
            elif response.status_code != 200:
                if hasattr(response,"reason"):
                    reason = response.reason
                else:
                    reason = "Unknown"
                if args.verbose:
                    print("...Failure.")
                    sys.exit(f'"Non OK response of "{response.status_code}" when POSTing app: "{f}" \nReason: "{reason}"\nAborting...')


    def sortSchemafiles(e):
        """
        Telling Solr to reload config with every schema file load is problematic.
          - slow
          - we don't know dependencies and reloading requires order

        However we have seen times when a synonyms or stopword file failed to load because a schema change
        had not been reloaded.  The 500 error complained about a missing znode called schema.xml

        While not perfect, ordering the files so that the end of the list has schema followed by solrconfig.xml
        seems to get around the ordering problem.  THis doesn't mean that a dependency going the other direction
        could not cause a problem though.  If that happens, a manual reload of individual files may be needed.

        :param e:
        :return:
        """
        # put signals and signals aggr collections first
        # Perhaps all auto-created collections should be listed here
        if not re.search("solrconfig.xml|schema",e):
            e = "1_" + e
        elif  re.search("schema",e):
            e = "2_" + e
        elif  re.search("schema",e):
            e = "3_" + e
        return e

    def sortCollection(e):
        # put signals and signals aggr collections first
        # Perhaps all auto-created collections should be listed here
        expr = "_signals_|_rewrite_"
        if appName is not None:
            expr = expr + f"|^{appName}_COL.json$|collections/{appName}_COL.json$"
        if re.search(expr,e):
            e = "1_" + e
        return e

    # GET the feature from the target and see if it's identical to what's queued for upload
    def isDuplicateFeature(url, feature,usr=None,pswd=None):
        usr = getDefOrVal(usr,args.user)
        pswd = getDefOrVal(pswd,args.password)
        auth = None
        headers = {"Content-Type": "application/json"}
        if args.jwt is not None:
            headers["Authorization"] = f'Bearer {args.jwt}'
        else:
            auth = requests.auth.HTTPBasicAuth(usr, pswd)

        try:
            response = requests.get(url, auth=auth, headers=headers, verify=isVerify())
            response.raise_for_status()
            currentFeature = json.loads(response.content)
            if args.debug:
                sprint(f"feature duplicate check = {currentFeature == feature}")
            return currentFeature == feature

        except Exception as ex:
            pass

        return False

    def putFeatures():
        apiUrl = makeBaseUri() + "/collections"
        files = getFileListing(os.path.join(args.dir,"collectionFeatures"),[])
        colfiles_o = getFileListForType("collections")
        colfiles = []
        for c in colfiles_o:
            if c.startswith("collections"):
                #remove an extra char for the path delim
                c = c.split("collections")[1][1:]
            colfiles.append(os.path.join(args.dir,"collectionFeatures",c.split('_COL.json')[0]))

        params = "_cookie=false"
        for f in files:
            # only process features that have a matching collection upload in the file list
            if f.endswith(f'{getSuffix("features")}') and f.split(getSuffix("features"))[0] in colfiles:

                with open(f, 'r') as jfile:
                    payload = json.load(jfile)
                    for feature in payload:
                        name = feature["name"]
                        col = feature["collectionId"]
                        url = f'{apiUrl}/{col}/features/{name}'
                        if isDuplicateFeature(url,feature):
                            if args.verbose:
                                sprint(f'Skipping "{name}" feature for collection "{col}" because it is unchanged.')
                            continue
                        try:
                            response = doHttpJsonPut(url, feature)
                            response.raise_for_status()
                            sprint(f'Successfully uploaded "{name}" feature for collection "{col}"')

                        except Exception as ex:
                            # some exceptions are ok because Fusion sends a 500 error if it can't delete non-existing collections
                            ex_text = ""
                            if hasattr(ex,'text'):
                                ex_text = ex["text"]
                            elif hasattr(ex,'response') and hasattr(ex.response,"text"):
                                ex_text = ex.response.text

                            search = re.search("Unable to (create|delete) (.*) collection",ex_text)

                            if search:
                              sprint(f'WARNING: dependent collection not deleted/created when feature "{name}" uploaded for collection "{col}"')
                            else:
                              eprint(f'Error putting "{name}" feature for collection "{col}". msg:\n\t{ex_text}')

    def putCollections():

        apiUrl = makeBaseUri() + "/collections"
        sortedFiles = sorted(getFileListForType("collections"),key=sortCollection)
        params = "_cookie=false"
        for f in sortedFiles:
            with open(os.path.join(args.dir,f), 'r') as jfile:
                payload = json.load(jfile);
                # pop off name for collections pointing at "default".  That way the local collections get created in Solr.
                # keep the name for external (non-default) collections since those only need the Fusion reference created.

                doPop = payload["solrParams"] and payload["searchClusterId"] == "default"

                # also keep if solrParams.name != the fusion name "id" and args.
                if payload["solrParams"] and payload['id'] != payload['solrParams']['name']:
                    doPop = False
                    debug("Not creating Solr collection named " + payload['solrParams']['name'] )
                if payload["type"] is not None and payload["type"] == "DATA":
                    params += "&defaultFeatures=false"

                if doPop:
                    payload["solrParams"].pop('name', None)
                if payload["searchClusterId"] == "default":
                    # to skip sub collections add defaultFeatures=false
                    response = doPostByIdThenPut(apiUrl, payload, 'Collection', putParams=params,postParams=params)
                    if response.status_code == 200:
                        if args.verbose:
                            sprint(f'Successfully uploaded collection definition for {payload["id"]}')

                        putSchema(payload['id'])

    #
    # invert the args.noVerify for readability
    #
    def isVerify():
      return not args.noVerify

    def doHttp(url,usr=None, pswd=None):
        usr = getDefOrVal(usr,args.user)
        pswd = getDefOrVal(pswd,args.password)
        auth = None
        headers = {}
        if args.jwt is not None:
            headers["Authorization"] = f'Bearer {args.jwt}'
        else:
            auth=requests.auth.HTTPBasicAuth(usr, pswd)

        response = None
        try:
            response = requests.get(url, auth=auth,headers=headers,verify=isVerify())
            return response
        except requests.ConnectionError as e:
            eprint(e)

    def doHttpJsonGet(url):
        response = doHttp(url)
        if response.status_code == 200:
            j = json.loads(response.content)
            return j
        else:
            if response.status_code == 401 and 'unauthorized' in response.text:
                eprint("Non OK response of " + str(response.status_code) + " for URL: " + url + "\nCheck your password\n")
            else:
                eprint("Non OK response of " + str(response.status_code) + " for URL: " + url)


    def getFileListing(path,removePathPrefix=True):
        """
        walk the file system and grab files

        :param path:
        :param fileList:
        :return: fileList relative to the working directory
        """
        #for root, dirs, files in os.walk(path,topdown=True):
            #for directory in dirs:
                #getFileListing(os.path.join(path,directory),fileList,directory)
            #    pass
        #    for file in files:
        #        addFile = os.path.join(dirs,file)
        #        if addFile not in fileList:
        #          fileList.append(addFile)
        pathList = list(Path(path).rglob("*"))
        # now make it a list of strings instead of posixPath objects
        fileList = []
        for p in pathList:
            if p.is_file():
                fstr = str(p)
                if removePathPrefix and len(path) > 0 and fstr.startswith(path):
                    # add 1 to the len of the path to remove the path separator
                    fstr = fstr[len(path) + 1:]
                fileList.append(fstr)
        return fileList

    def putSchema(colName):
        schemaUrl = args.server + "/api"
        schemaUrl += "/collections/" + colName + "/solr-config"
        currentZkFiles = []
        # get a listing of current files via Fusion's solr-config api. This prevents uploading directories which don't exist (unsupported)
        # this listing needs to look like the relative path of the files themselves so that an existence check can be done for Put vs Post
        zkFilesJson = doHttpJsonGet(schemaUrl + "?recursive=true")
        if zkFilesJson and len(zkFilesJson) > 0:
            for obj in zkFilesJson:
                if not obj['isDir']:
                    currentZkFiles.append(obj['name'])
                else:
                    for child in obj['children']:
                        if not child['isDir']:
                            currentZkFiles.append(os.path.join(obj['name'],child['name']))


        dir = os.path.join(args.dir, "configsets", colName )
        files = sorted(getFileListing(dir),key=sortSchemafiles)

        counter = 0;

        if len(files) > 0:
            sprint("\nUploading Solr config for collection: " + colName)
        for file in files:
            counter += 1
            #if the file is part of the current configset and is available for upload, upload it.
            pathFile = os.path.join(args.dir,"configsets",colName,file)
            if os.path.isfile(pathFile):
                isLast = len(files) == counter
                # see if the file exists and PUT or POST accordingly
                url = schemaUrl + '/' + file.replace(os.sep,'/')
                if isLast:
                    url += '?reload=true'
                #PUT to update, POST to add
                try:
                    response = doHttpPostPut(url, pathFile, (file in currentZkFiles))
                    response.raise_for_status()
                    if args.verbose:
                        sprint("\tUploaded " + file + " successfully")
                        if isLast:
                            sprint("\tSent reload=true to collection " + colName)
                except Exception as e:

                    if hasattr(e,"response") and e.response.status_code:
                        eprint("Non OK response: " + str(e.response.status_code) + " when uploading " + file)
                    elif hasattr(e,"response"):
                        r = e.response
                        msg = None
                        if hasattr(r,"msg"):
                            msg = r.msg
                        elif hasattr(e,'text'):
                            msg = r["text"]
                        else:
                            msg = str(e)
                            eprint(f"Error uploading {colName} configset file {file}. Msg: {msg}")
                    else:
                        msg = str(e)
                        eprint(f"Error uploading {colName} configset file {file}. Msg: {msg}")
            else:
                sprint(f"WARN: scan of {dir} for files found non-file {file}")


    def eprint(*params, **kwargs):
        print(*params, file=sys.stderr, **kwargs)
        if args.failOnStdError:
            sys.exit("Startup argument --failOnStdErr set, exiting putApp")

    def sprint(msg):
        # change inputs to *args, **kwargs in python 3
        #print(*args, file=sys.stderr, **kwargs)
        print(msg)
        sys.stdout.flush()

    def debug(msg):
        if args.debug:
            sprint(msg)


    # populate the fileList global with arrays of files to put
    def findFiles():
        files = os.listdir(args.dir)
        for f in files:
            inferType = inferTypeFromFile(f)
            if inferType:
                # grab the global filelist array for this type and stuff in the filename
                flist = getFileListForType(inferType)
                if isinstance( flist, (list )):
                    flist.append(f)
            elif f in OBJ_TYPES:
                dfiles = os.listdir(os.path.join(args.dir,f))
                for df in dfiles:
                    inferType = inferTypeFromFile(df)
                    if inferType:
                        # grab the global filelist array for this type and stuff in the filename
                        flist = getFileListForType(inferType)
                        if isinstance( flist, (list )):
                            flist.append(os.path.join(f,df))



    def putJobSchedules():
        type = "jobs"
        apiUrl = makeBaseUri() + "/" + getApiForType(type) + "/"
        for f in getFileListForType(type):
            with open(os.path.join(args.dir,f), 'r') as jfile:
                payload = json.load(jfile)
                url = apiUrl + payload['resource'] + '/schedule'
                response = doHttpPostPut(url, os.path.join(args.dir,f), True)
                if response.status_code == 200:
                    if args.verbose:
                        sprint( "Created/updated Job schedule from " + f)
                # allow a 404 since we are using the /apollo/apps/{collection} endpoint but the export gives us global jobs as well
                elif response.status_code != 200 and response.status_code != 404:
                    eprint("Non OK response of " + str(response.status_code) + " when PUTing: " + url)
    def mergeReadableScript(element,rawTag):
        mergetag = rawTag + TAG_SUFFIX
        if mergetag in element:
            script = "\n".join(element[mergetag])
            element[rawTag] = script  ##overwrite script with the version used in diff/merge
            element.pop(mergetag,None)

    def migrateReadableScript(data,type):
        xformTags = [
            "script" + TAG_SUFFIX # scala script, python
            ,"transformScala" + TAG_SUFFIX # PBL
            ,"transformSQL" + TAG_SUFFIX # PBL
            ,"sql" + TAG_SUFFIX # sqlTemplate
            ,"sparkSQL" + TAG_SUFFIX # sqlTemplate, headTail, tokenPhraseSpellCorrection
            ,"misspellingSQL" + TAG_SUFFIX # synonym detection
            ,"phraseSQL" + TAG_SUFFIX # synonym detection
            ,"rollupSql" + TAG_SUFFIX # sql_template
            #,"analyzerConfigQuery" + TAG_SUFFIX # candidate json from some 4 sisters
            #,"notes" + TAG_SUFFIX # candidate for multi-line descript/notes field
        ]

        if isinstance(data,dict) and type.endswith("Pipelines") and ('stages' in data ):
            for stage in data['stages']:
                if isinstance(stage,dict) and ('script' in stage):
                    if ('script' + TAG_SUFFIX) in stage:
                        mergeReadableScript(stage,"script")
                    if ('condition' + TAG_SUFFIX) in stage:
                        mergeReadableScript(stage,'condition')
        elif isinstance(data,dict) and type == "sparkJobs":
            for tag in xformTags:
                if tag in data:
                    mergeReadableScript(data,tag.split("_")[0])

    def putFileForType(type,forceLegacy=False, idField=None, existsChecker=None ):
        if not idField:
            idField = 'id'
        apiUrl = makeBaseUri(forceLegacy) + "/" + getApiForType(type)
        for f in getFileListForType(type):
            with open(os.path.join(args.dir,f), 'r') as jfile:
                payload = json.load(jfile)
                if isSubstitutionType(type):
                    if args.verbose and isinstance(varReplacements, dict):
                        sprint("Doing substitution for file " + f)
                    payload = traverseAndReplace(payload,f, varReplacements)

                migrateReadableScript(payload,type)
                #doPostByIdThenPut(apiUrl, payload, type,None, idField)
                doPostByIdThenPut(apiUrl, payload, type,None,None,idField,None,None,existsChecker)

    def putTemplateFileForType(type, idField=None, existsChecker=None ):
        if not idField:
            idField = 'id'
        base = args.server + "/"
        apiUrl = base + getApiForType(type)
        for f in getFileListForType(type):
            with open(os.path.join(args.dir,f), 'r') as jfile:
                payload = json.load(jfile)
                if isSubstitutionType(type):
                    if args.verbose is not None and isinstance(varReplacements, dict):
                        sprint("Doing substitution for file " + f)
                    payload = traverseAndReplace(payload,f, varReplacements)

                migrateReadableScript(payload,type)
                #doPostByIdThenPut(apiUrl, payload, type,None, idField)
                doPostByIdThenPut(apiUrl, payload, type,None,None,idField,None,None,existsChecker)

    def doHttpJsonPut(url,payload, usr=None, pswd=None):
        usr = getDefOrVal(usr,args.user)
        pswd = getDefOrVal(pswd,args.password)
        headers = {'Content-Type': "application/json"}
        auth = None
        if args.jwt is not None:
            headers["Authorization"] = f'Bearer {args.jwt}'
        else:
            auth=requests.auth.HTTPBasicAuth(usr, pswd)
        try:
            response = requests.put(url, auth=auth,headers=headers, data=json.dumps(payload))
            return response
        except requests.ConnectionError as e:
            eprint(e)


    def fetchFusionVersion():
        global fusionVersion
        url = makeBaseUri() + "/configurations"
        configurations = doHttpJsonGet(url)
        if configurations is not None and configurations["app.version"]:
            fusionVersion = configurations["app.version"]

    def main():
        initArgs()
        fetchFusionVersion()

        # fetch collections first
        sprint("Uploading objects found under '" + args.dir + "' to Fusion version " + fusionVersion)
        sprint(f'Upload target API: {makeBaseUri()}')

        findFiles()
        # putApps must be the first export, clusters next.  blobs and collections in either order then pipelines
        putApps()


        putCollections()
        putFeatures()
        putBlobs()

        putFileForType('parsers')
        putFileForType('indexPipelines')
        putFileForType('queryPipelines')
        putFileForType('indexProfiles')
        putFileForType('queryProfiles')
        putFileForType('tasks')
        putFileForType('sparkJobs',None,None,lambda r,p: sparkChecker(r,p))

        putFileForType("dataSources",None,None,lambda r,p: datasourceChecker(r,p))
        putJobSchedules()

        putTemplateFileForType('zones')
        putTemplateFileForType('templates')
        putFileForType('dataModels')

    def sparkChecker(response,payload):
        exists = False
        status = response.status_code
        text = response.text;
        exists = status == 409
        if not exists:
            exists = ( status == 500 or status == 400) and text.find( payload['id'] +" already exists") > 0
        return exists

    def datasourceChecker(response,payload):
        #old fusion sends 409, 4.1 500, 4.2 400
        exists = False
        status = response.status_code
        text = response.text;
        exists = status == 409
        if not exists:
            exists = ( status == 500 or status == 400) and text.find("Data source id '" + payload['id'] +"' already exists") > 0
        return exists

    if __name__ == "__main__":
        scriptName = os.path.basename(__file__)
        # sample line: 'usage: putProject.py [-h] [-d DIR] [-s SERVER]'
        description = ('______________________________________________________________________________\n'
                    'Take a folder containing .json files (produced by getApp.py) and POST the contents \n'
                    'to a Fusion instance.  App and Collection definitions will be created/modified as needed, \n'
                    'as will Pipelines, Parsers, Profiles and Datasources. \n'
                    '______________________________________________________________________________'
                       )

        parser = argparse.ArgumentParser(description=description, formatter_class=RawTextHelpFormatter )

        parser.add_argument("-d","--dir", help="Input directory, required.", required=True)#,default="default"
        parser.add_argument("--failOnStdError",help="Exit the program if StdErr is written to i.e. fail when any call fails.",default=False,action="store_true")
        parser.add_argument("-s","--server", metavar="SVR", help="Fusion server to send data to. Default: ${lw_OUT_SERVER} or 'localhost'.") # default="localhost"
        parser.add_argument("-u","--user", help="Fusion user, default: ${lw_USER} or 'admin'.") #,default="admin"
        parser.add_argument("--password", help="Fusion password,  default: ${lw_PASSWORD} or 'password123'.") #,default="password123"
        parser.add_argument("--jwt",help="JWT token for authentication.  If set, password is ignored",default=None)

        parser.add_argument("--debug",help="Print debug messages while running, default: False.",default=False,action="store_true")# default=False
        parser.add_argument("--noVerify",help="Do not verify SSL certificates if using https, default: False.",default=False,action="store_true")# default=False
        parser.add_argument("-v","--verbose",help="Print details, default: False.",default=False,action="store_true")# default=False
        parser.add_argument("--varFile",help="Protected variables file used for password replacement (if needed) default: None.",default=None)

        args = parser.parse_args()
        main()

except ImportError as ie:
    print("Failed to Import from module: ",
          ie.name,
          "\ninstall the module via the pip installer\n\nExample:\n\t$ pip3 install ",
          ie.name, file=sys.stderr)
    sys.exit(1)
except Exception as e:
    msg = None
    if hasattr(e,"msg"):
        msg = e.msg
    elif hasattr(e,'text'):
            msg = e["text"]
    elif hasattr(e,'txt'):
        msg = e["txt"]
    else:
        msg = str(e)

    print("Exception: " + msg, file=sys.stderr)
    sys.exit("1")