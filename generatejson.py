#!/usr/bin/python
# -*- coding: utf-8 -*-

# Generate Json file for installapplications
# Usage: python generatejson.py --rootdir /path/to/rootdir
#
# --rootdir path is the directory that contains each stage's pkgs directory
# As of InstallApplications 5/28/17, the directories must be named (lowercase):
#   'prestage', 'stage1', and 'stage2'
#
# The generated Json will be saved in the root directory
#
# If you have AWS S3 and would like to host your packages and bootstrap.json
# there, you can take advantage of the --s3 aption and supply your access
# credentials via json template or command line arguments

import hashlib
import json
import argparse
import os
import sys

iapath = "/private/tmp/installapplications/"
bsname = "bootstrap.json"


def gethash(filename):
    # Credit to Erik Gomez
    hash_function = hashlib.sha256()
    fileref = open(filename, 'rb')
    while 1:
        chunk = fileref.read(2**16)
        if not chunk:
            break
        hash_function.update(chunk)
    fileref.close()
    return hash_function.hexdigest()


def import_template(template):
    # This function borrowed from Vfuse, thanks Joseph Chilcote
    try:
        with open(template) as f:
            try:
                d = json.load(f)
            except ValueError as err:
                print 'Unable to parse %s\nError: %s' % (template, err)
                sys.exit(1)
    except NameError as err:
        print '%s; bailing script.' % err
        sys.exit(1)
    except IOError as err:
        print '%s: %s' % (err.strerror, template)
        sys.exit(1)
    return d


def s3upload(s3, filepath, bucket, filename, mime="application/octetstream"):
    s3.upload_file(filepath, bucket, filename,
                   ExtraArgs={'ACL': 'public-read', 'ContentType': mime})
    s3url = s3.generate_presigned_url(ClientMethod='get_object',
                                      Params={
                                        'Bucket': bucket,
                                        'Key': filename
                                      })
    url = s3url.split("?", 1)[0]
    print "Uploaded %s to %s" % (filename, bucket)
    return url


def main():
    ap = argparse.ArgumentParser(description='This tool generates \
                                 bootstrap.json for InstallApplications')
    requiredgroup = ap.add_argument_group('required arguments:')
    requiredgroup.add_argument('-r', '--rootdir', help=(
        'Required: Root directory path for InstallApplications stages'))
    ap.add_argument('-s', '--s3', action="store_true", help=(
        'Optional: Enable S3 upload'))
    configgroup = ap.add_argument_group('AWS S3 Configuration File (--s3 req)')
    configgroup.add_argument('-c', '--s3configpath', default=None, help=(
        'Set path to AWS S3 configuration json file.'))
    inlineconfig = ap.add_argument_group('AWS S3 Access Arguments (--s3 req)')
    inlineconfig.add_argument('-a', '--awsaccesskey', default=None, help=(
        'Set AWS Access Key.'))
    inlineconfig.add_argument('-k', '--awssecretkey', default=None, help=(
        'Set AWS Secret Access Key.'))
    inlineconfig.add_argument('-g', '--s3region', default=None, help=(
        'Set S3 region (e.g. us-east-2).'))
    inlineconfig.add_argument('-b', '--s3bucket', default=None, help=(
        'Set S3 bucket name.'))
    args = ap.parse_args()

    if args.rootdir and not args.s3:
        rootdir = args.rootdir
        uploadtos3 = False
    elif args.rootdir and args.s3 and args.s3configpath:
        rootdir = args.rootdir
        d = import_template(args.s3configpath)
        if d.get('awsaccesskey'):
            awsaccesskey = d['awsaccesskey']
        else:
            print "Missing AWS Access key in Config file (awsaccesskey)"
            sys.exit(1)
        if d.get('awssecretkey'):
            awssecretkey = d['awssecretkey']
        else:
            print "Missing AWS Secret key in Config file (awssecretkey)"
            sys.exit(1)
        if d.get('s3region'):
            s3region = d['s3region']
        else:
            print "Missing S3 Region key in Config file (s3region)"
            sys.exit(1)
        if d.get('s3bucket'):
            s3bucket = d['s3bucket']
        else:
            print "Missing S3 Bucket key in Config file (s3bucket)"
            sys.exit(1)

        try:
            import boto3
        except ImportError:
            print "For S3 Upload, please install Boto3 (pip install boto3)"
            sys.exit(1)

        s3 = boto3.client('s3', region_name=s3region,
                          aws_access_key_id=awsaccesskey,
                          aws_secret_access_key=awssecretkey)
        uploadtos3 = True
    elif args.rootdir and args.s3 and not args.s3configpath:
        rootdir = args.rootdir
        if args.awsaccesskey:
            awsaccesskey = args.awsaccesskey
        else:
            print "Please provide an AWS Access Key with -a or --awsaccesskey"
            sys.exit(1)
        if args.awssecretkey:
            awssecretkey = args.awssecretkey
        else:
            print ("Please provide an AWS Secret Access Key with -k or "
                   "--awssecretkey")
            sys.exit(1)
        if args.s3region:
            s3region = args.s3region
        else:
            print ("Please provide a S3 Region (e.g. us-east-2) with -g or "
                   "--s3region")
            sys.exit(1)
        if args.s3bucket:
            s3bucket = args.s3bucket
        else:
            print "Please provide a S3 Bucket name with -b or --s3bucket"
            sys.exit(1)

        try:
            import boto3
        except ImportError:
            print "Please install Boto3 (pip install boto3)"
            sys.exit(1)

        s3 = boto3.client('s3', region_name=s3region,
                          aws_access_key_id=awsaccesskey,
                          aws_secret_access_key=awssecretkey)
        uploadtos3 = True
    else:
        ap.print_help()
        sys.exit(1)

    # Traverse through root dir, find all stages and all pkgs to generate json
    stages = {}
    expected_stages = ['prestage', 'stage1', 'stage2']
    for subdir, dirs, files in os.walk(rootdir):
        for d in dirs:
            if d in expected_stages:
                stages[str(d)] = []
            else:
                print "Ignoring files in directory: %s" % d
        for file in files:
            filepath = os.path.join(subdir, file)
            filestage = os.path.basename(os.path.abspath(
                                         os.path.join(filepath, os.pardir)))
            if file.endswith('.pkg') and filestage in expected_stages:
                filename = os.path.basename(filepath)
                filehash = gethash(filepath)
                if uploadtos3:
                    fileurl = s3upload(s3, filepath, s3bucket, filename)
                    filejson = {"file": iapath + filename, "url": fileurl,
                                "hash": str(filehash)}
                else:
                    filejson = {"file": iapath + filename, "url": "",
                                "hash": str(filehash)}
                stages[filestage].append(filejson)

    # Saving the bootstrap json in the root dir
    bspath = os.path.join(rootdir, bsname)
    with open(bspath, 'w') as outfile:
        json.dump(stages, outfile, sort_keys=True, indent=2)

    print "Json saved to %s" % bspath

    if uploadtos3:
        bsurl = s3upload(s3, bspath, s3bucket, bsname, "application/json")
        print "\nJson URL for InstallApplications is %s" % bsurl


if __name__ == '__main__':
    main()
