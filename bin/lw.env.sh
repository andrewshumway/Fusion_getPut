#!/usr/bin/env bash

# 
# these environment variables drive curl and other commands.  Replace as needed
#  Note the -z if blocks.  If the variable is already defined in the parent shell
# it will not be redefined.

#################
#  ON WINDOWS ENVIRONMENTS such as git-bash
# the python scripts will not pick up these values.  To work around this push an extra bash shell
# and source this file manually before running the python script
###############################################


################################################
#  The PREFIX and COLLECTION settings define the set of Fusion objects to work with.  COLLECTION is used
#  on datasource APIs because datasources are tied to a COLLECTION.
#
#  PREFIX is very important.  Datasources, or Pipelines with a name/id begining witht he PREFIX value will be
#  searched, or exported by scripts.  For example: with the default PREFIX value of 'lwes_' the 'exportPipelines.ph'
#  script will list or export all Datasources, Index Pipelines, and Query Pipelines who's name begines with 'lwes_'
##############################################

if [ -z "$lw_OUT_SERVER" ] ; then
    export lw_OUT_SERVER="https://localhost"
fi
if [ -z "$lw_IN_SERVER" ] ; then
    export lw_IN_SERVER="https://localhost"
fi
if [ -z "$lw_USERNAME" ] ; then
    export lw_USERNAME="admin"
fi
if [ -z "$lw_PASSWORD" ] ; then
    export lw_PASSWORD="password123"
fi

######
#  set the encoding or you get IO errors on windows
######
if [ -z "$PYTHONIOENCODING" ]; then
    export PYTHONIOENCODING=UTF-8
fi
