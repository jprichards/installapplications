#!/usr/bin/python
# -*- coding: utf-8 -*-

# Generate Json file for installapplications
# Usage: python generatejson.py --rootdir /path/to/rootdir
#
# --rootdir path is the directory that contains each stage's pkgs directory
# As of InstallApplications 5/29/17, the directories must be named (lowercase):
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

iapath = '/private/tmp/installapplications/'
bsname = 'bootstrap.json'


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
    # From Vfuse, credit to Joseph Chilcote
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


def s3upload(s3, filepath, bucket, filename, mime='application/octetstream'):
    # Currently defaulted to make public on upload
    # S3UploadFailedError

    s3.upload_file(filepath, bucket, filename,
                   ExtraArgs={'ACL': 'public-read', 'ContentType': mime})
    s3url = s3.generate_presigned_url(ClientMethod='get_object',
                                      Params={'Bucket': bucket,
                                              'Key': filename})
    url = s3url.split('?', 1)[0]
    print 'Uploaded %s to %s' % (filename, bucket)
    return url


def main():
    ap = argparse.ArgumentParser(description='This tool generates \
                                 bootstrap.json for InstallApplications')

    maingroup = ap.add_argument_group('main arguments')
    maingroup.add_argument('-r', '--rootdir', help=(
        'required: root directory path for InstallApplications stages'))
    maingroup.add_argument('-o', '--outputdir', help=(
        'optional: output directory to save json, default saves in the rootdir'))

    ap.add_argument('-s', '--s3', action='store_true', help=(
        'optional: enable S3 upload'))

    cfilegroup = ap.add_argument_group('AWS S3 Configuration File (--s3 req)')
    cfilegroup.add_argument('-c', '--s3configpath', default=None, help=(
        'set path to configuration json file containing AWS access keys &\
        S3 settings.'))

    inlineconf = ap.add_argument_group('AWS S3 Access Arguments (--s3 req)')
    inlineconf.add_argument('-a', '--awsaccesskey', default=None, help=(
        'set AWS Access Key.'))
    inlineconf.add_argument('-k', '--awssecretkey', default=None, help=(
        'set AWS Secret Access Key.'))
    inlineconf.add_argument('-g', '--s3region', default=None, help=(
        'set S3 region (e.g. \'us-east-2\').'))
    inlineconf.add_argument('-b', '--s3bucket', default=None, help=(
        'set S3 bucket name.'))
    inlineconf.add_argument('-f', '--s3bucketfolder', default=None, help=(
        'set S3 bucket folder path (e.g. \'path/to/folder/\' ).'))
    inlineconf.add_argument('-u', '--jsons3bucket', default=None, help=(
        'set JSON S3 bucket name.'))
    inlineconf.add_argument('-l', '--jsons3bucketfolder', default=None, help=(
        'set JSON S3 bucket folder path (e.g. \'path/to/folder/\' ).'))
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
            print 'Missing AWS Access key in Config file (awsaccesskey)'
            sys.exit(1)
        if d.get('awssecretkey'):
            awssecretkey = d['awssecretkey']
        else:
            print 'Missing AWS Secret key in Config file (awssecretkey)'
            sys.exit(1)
        if d.get('s3region'):
            s3region = d['s3region']
        else:
            print 'Missing S3 Region key in Config file (s3region)'
            sys.exit(1)
        if d.get('s3bucket'):
            s3bucket = d['s3bucket']
        else:
            print 'Missing S3 Bucket key in Config file (s3bucket)'
            sys.exit(1)

        if d.get('s3bucketfolder'):
            s3bucketfolder = d['s3bucketfolder']
            bucketfolder = True
        if d.get('json_s3bucket'):
            jsons3bucket = d['json_s3bucket']
            jbucket = True
        else:
            jbucket = False
        if d.get('json_s3bucketfolder'):
            jsons3bucketfolder = d['json_s3bucketfolder']
            jfolder = True
        else:
            jfolder = False

        try:
            import boto3
        except ImportError:
            print 'For S3 Upload, please install Boto3 (pip install boto3)'
            sys.exit(1)

        s3 = boto3.client('s3', region_name=s3region,
                          aws_access_key_id=awsaccesskey,
                          aws_secret_access_key=awssecretkey)
        uploadtos3 = True

        if jbucket or jfolder:
            json_s3 = boto3.client('s3', region_name=s3region,
                                   aws_access_key_id=awsaccesskey,
                                   aws_secret_access_key=awssecretkey)
            jsons3 = True
        else:
            jsons3 = False


    elif args.rootdir and args.s3 and not args.s3configpath:
        rootdir = args.rootdir
        if args.awsaccesskey:
            awsaccesskey = args.awsaccesskey
        else:
            print 'Please provide an AWS Access Key with -a or --awsaccesskey'
            sys.exit(1)
        if args.awssecretkey:
            awssecretkey = args.awssecretkey
        else:
            print ('Please provide an AWS Secret Access Key with -k or '
                   '--awssecretkey')
            sys.exit(1)
        if args.s3region:
            s3region = args.s3region
        else:
            print ('Please provide a S3 Region (e.g. us-east-2) with -g or '
                   '--s3region')
            sys.exit(1)
        if args.s3bucket:
            s3bucket = args.s3bucket
        else:
            print 'Please provide a S3 Bucket name with -b or --s3bucket'
            sys.exit(1)
        if args.s3bucketfolder:
            s3bucketfolder = args.s3bucketfolder
            bucketfolder = True
        else:
            bucketfolder = False
        if args.json_s3bucket:
            jsons3bucket = args.json_s3bucket
            jbucket = True
        else:
            jbucket = False
        if args.json_s3bucketfolder:
            jsons3bucketfolder = args.json_s3bucketfolder
            jfolder = True
        else:
            jfolder = False


        try:
            import boto3
        except ImportError:
            print 'Please install Boto3 (pip install boto3)'
            sys.exit(1)

        s3 = boto3.client('s3', region_name=s3region,
                          aws_access_key_id=awsaccesskey,
                          aws_secret_access_key=awssecretkey)
        uploadtos3 = True

        if jbucket or jfolder:
            json_s3 = boto3.client('s3', region_name=s3region,
                                   aws_access_key_id=awsaccesskey,
                                   aws_secret_access_key=awssecretkey)
            jsons3 = True
        else:
            jsons3 = False
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
                print 'Ignoring files in directory: %s' % d
        for file in files:
            filepath = os.path.join(subdir, file)
            filestage = os.path.basename(os.path.abspath(
                                         os.path.join(filepath, os.pardir)))
            if file.endswith('.pkg') and filestage in expected_stages:
                filename = os.path.basename(filepath)
                filehash = gethash(filepath)
                if uploadtos3:
                    if bucketfolder:
                        bpath = os.path.join(s3bucketfolder, filename)
                        fileurl = s3upload(s3, filepath, s3bucket, bpath)
                        filejson = {'file': iapath + filename, 'url': fileurl,
                                    'hash': str(filehash), 'name': filename}
                    else:
                        fileurl = s3upload(s3, filepath, s3bucket, filename)
                        filejson = {'file': iapath + filename, 'url': fileurl,
                                    'hash': str(filehash), 'name': filename}
                else:
                    filejson = {'file': iapath + filename, 'url': '',
                                'hash': str(filehash), 'name': filename}
                stages[filestage].append(filejson)

    # Save the JSON in the outputdir or rootdir
    if args.outputdir:
        savepath = os.path.join(args.outputdir, bsname)
    else:
        savepath = os.path.join(rootdir, bsname)
    try:
        with open(savepath, 'w') as outfile:
            json.dump(stages, outfile, sort_keys=True, indent=2)
    except IOError:
        print '[Error] Not a valid directory: %s' % savepath
        sys.exit(1)
    print '\nJson saved to %s' % savepath

    # Upload bootstrap.json to S3 if enabled
    if uploadtos3:
        if jsons3:
            if jfolder and jbucket:
                bpath = os.path.join(jsons3bucketfolder, bsname)
                bsurl = s3upload(json_s3, savepath, jsons3bucket, bpath, 'application/json')
                print('\n\x1b[34m' + 'Json URL for InstallApplications is %s' % bsurl +
                      '\x1b[0m\n')
            elif jfolder and not jbucket:
                bpath = os.path.join(jsons3bucketfolder, bsname)
                bsurl = s3upload(json_s3, savepath, s3bucket, bpath, 'application/json')
                print('\n\x1b[34m' + 'Json URL for InstallApplications is %s' % bsurl +
                      '\x1b[0m\n')
            elif jbucket and not jfolder:
                bsurl = s3upload(json_s3, savepath, jsons3bucket, bsname, 'application/json')
                print('\n\x1b[34m' + 'Json URL for InstallApplications is %s' % bsurl +
                      '\x1b[0m\n')
        else:
            bsurl = s3upload(s3, savepath, s3bucket, bsname, 'application/json')
            print('\n\x1b[34m' + 'Json URL for InstallApplications is %s' % bsurl +
              '\x1b[0m\n')


if __name__ == '__main__':
    main()
