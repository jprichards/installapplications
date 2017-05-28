#!/usr/bin/python
# -*- coding: utf-8 -*-

# Generate Json file for installapplications
# Usage: python generatejson.py --rootdir /path/to/rootdir
#
# --rootdir path is the directory that contains each stage's pkgs directory
# As of InstallApplications 5/13/17, the directories must be named (lowercase):
#   'prestage', 'stage1', and 'stage3'
#
# The generated Json will be saved in the root directory

import hashlib
import json
import optparse
import os
import sys

iapath = "/private/tmp/installapplications/"
bsname = "bootstrap.json"


def gethash(filename):
    # This code borrowed from InstallApplications, thanks Erik Gomez
    hash_function = hashlib.sha256()
    if not os.path.isfile(filename):
        return 'NOT A FILE'

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
    '''Imports user-defined template'''
    try:
        with open(template) as f:
            try:
                d = json.load(f)
            except ValueError as err:
                print colored('Unable to parse %s\nError: %s' %
                              (template, err), 'red')
                sys.exit(1)
    except NameError as err:
        print colored('%s; bailing script.' % err, 'red')
        sys.exit(1)
    except IOError as err:
        print colored('%s: %s' % (err.strerror, template), 'red')
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
    usage = '%prog --rootdir /path/to/dir/ [options]'
    op = optparse.OptionParser(usage=usage)
    op.add_option('--rootdir', help=(
        'Required: Root directory path for InstallApplications stages'))
    op.add_option('--s3', action="store_true", help=(
        'Optional: Enable S3 upload'))
    op.add_option('--s3configfile', default=None, help=(
        'Set path to AWS S3 config json. Requires S3 option'))
    op.add_option('--awsaccesskey', default=None, help=(
        'Set AWS Access Key. Requires S3 option'))
    op.add_option('--awssecretkey', default=None, help=(
        'Set AWS Secret Access Key. Requires S3 option'))
    op.add_option('--s3region', default=None, help=(
        'Set S3 region (e.g. us-east-2). Requires S3 option'))
    op.add_option('--s3bucket', default=None, help=(
        'Set S3 bucket name. Requires S3 option'))
    opts, args = op.parse_args()

    if opts.rootdir and not opts.s3:
        rootdir = opts.rootdir
        uploadtos3 = False
    elif opts.rootdir and opts.s3 and opts.s3configfile:
        rootdir = opts.rootdir
        d = import_template(opts.s3configfile)
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
            print "Please install Boto3 (pip install boto3)"
            sys.exit(1)

        s3 = boto3.client('s3', region_name=s3region,
                          aws_access_key_id=awsaccesskey,
                          aws_secret_access_key=awssecretkey)
        uploadtos3 = True
    elif opts.rootdir and opts.s3 and not opts.s3configfile:
        rootdir = opts.rootdir
        if opts.awsaccesskey:
            awsaccesskey = opts.awsaccesskey
        else:
            print "Please provide an AWS Access Key with --awsaccesskey"
            sys.exit(1)
        if opts.awssecretkey:
            awssecretkey = opts.awssecretkey
        else:
            print "Please provide an AWS Secret Access Key with --awssecretkey"
            sys.exit(1)
        if opts.s3region:
            s3region = opts.s3region
        else:
            print "Please provide a S3 Region (e.g. us-east-2) with --s3region"
            sys.exit(1)
        if opts.s3bucket:
            s3bucket = opts.s3bucket
        else:
            print "Please provide a S3 Bucket name with --s3bucket"
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
        op.print_help()
        sys.exit(1)

    # Traverse through root dir, find all stages and all pkgs to generate json
    stages = {}
    for subdir, dirs, files in os.walk(rootdir):
        for d in dirs:
            stages[str(d)] = []
        for file in files:
            if file.endswith('.pkg'):
                filepath = os.path.join(subdir, file)
                filename = os.path.basename(filepath)
                filehash = gethash(filepath)
                filestage = os.path.basename(os.path.abspath(
                            os.path.join(filepath, os.pardir)))
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

    print "Json saved to root directory"

    if uploadtos3:
        bsurl = s3upload(s3, bspath, s3bucket, bsname, "application/json")
        print "Json URL for InstallApplications is %s  " % bsurl


if __name__ == '__main__':
    main()
