#!/bin/bash

##########################################################################
#
# CONVERT MSG TO EML
#
##########################################################################
#
# This is a script for batch converting "*.msg" files to => "*.eml" files.
# The script processes all "*.eml" files found in the scripts folder.
#
# Author: Michael Schmid <m.schmid@si-ne.org>
# Version: 2020-08-12
#
##########################################################################

clear

# (Optional) Specify a custom subfolder where your MSG files are stored:
# MSG_FOLDER="TheHive Converter Samples"
# cd "$MSG_FOLDER"

for f in *.msg; do
	FILENAME_MSG=`echo "$f" | sed 's/ /\\ /g'`
	echo "DOING File: '$FILENAME_MSG'"

	FILENAME_EML=`echo "$FILENAME_MSG" | sed 's/.msg/.eml/g'`
	echo "MSGCONVERT to EML file: '$FILENAME_EML'"
	MSGC_OUTPUT=$( msgconvert --outfile "$FILENAME_EML" "$FILENAME_MSG" 2>&1 )

	if [[ ! -z "$MSGC_OUTPUT" ]]
	then
		echo "MSGCCONVERT Error:"
		echo "=> $MSGC_OUTPUT"
	fi

	echo "DONE."
	echo ""
done
