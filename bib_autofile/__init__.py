#!/usr/bin/env python3
# coding: utf-8

# TODO:
#  - Find the bib key using XMP data (exiftool -a -G1 xxx.pdf)

from __future__ import print_function

import os
import re
import sys
import time
import arxiv
import codecs
import shutil
import logging

from clint import resources
from clint.textui import prompt
import configargparse as argparse

import pybtex.errors
# Configure pybtex such that errors are silent
pybtex.errors.set_strict_mode(False)
def silent(*args, **kargs):
    pass
pybtex.errors.print_error = silent
from pybtex.database.input import bibtex
from pybtex.database import BibliographyData, Entry
from pybtex.database import parse_string as parse_bibtex_string

from habanero import cn

resources.init("fg1", "bib_autofile")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def parse_args():
    parser = argparse.ArgumentParser(description="bibtex helper", default_config_files=[os.path.join(resources.user.path, "config.ini")])
    parser.add_argument("ref", type=str)
    parser.add_argument("-k", dest="bibkey", default="last", type=str)
    parser.add_argument("--bibfile", help="Bibliography file", type=str)
    parser.add_argument("--pdfsdir", help="Directory with PDFs", type=str)
    parser.add_argument("--pdfformat", help="Which format should be used for the name of the PDF", default="%(ID)s - %(title)s", type=str)
    parser.add_argument("--timestamp-format", default="{}.{:02d}.{:02d}", type=str)
    parser.add_argument("-o", dest="overwrite", action="store_true", help="Overwrites the file in the bibtex entry")
    parser.add_argument("-r", dest="disable_rename", action="store_true", help="Disable renaming of the PDF file")
    parser.add_argument("-d", dest="dryrun", action="store_true", help="Do not perform actions")
    return parser.parse_args()


def parse_bibtex(args):
    if args.bibfile is None:
        print("No bibtex file configured!")
        sys.exit(1)

    if not os.path.exists(args.bibfile):
        print("No bibtex file found at:", args.bibfile)
        sys.exit(1)

    parser = bibtex.Parser()
    with codecs.open(args.bibfile, "r", "utf-8") as fhandle:
        bdn = parser.parse_file(fhandle)
    return bdn


def find_bibentry(args, bdn):
    if args.bibkey == "last":
        s = sorted(bdn.entries.values(), key=lambda e: (e.fields["timestamp"], e.key), reverse=True)
        if not args.overwrite:
            s = list(filter(lambda e: "file" not in e.fields, s))
        ltstamp = s[0].fields["timestamp"]
        s = list(filter(lambda e: e.fields["timestamp"] == ltstamp, s))

        if len(s) == 1:
            vars(args)["bibkey"] = s[0].key
        else:
            choices = []
            i = 0
            for e in s:
                choices.append({"selector": i, "prompt": "%s - %s" % (e.key, e.fields["title"]), "return": e.key})
                i += 1
            vars(args)["bibkey"] = prompt.options("Which entry?", choices)

    # Check that the key which is specified exists
    if args.bibkey not in bdn.entries:
        logger.fatal("Couldn't find key '%s' in bibtex file" % args.bibkey)
        return None
    return bdn.entries[args.bibkey]


def find_dup_entry(bdn, field, val):
    val_ = val.lower()
    for bibkey, e in bdn.entries.items():
        if field in e.fields and e.fields[field].lower() == val_:
            return bibkey, e


def check_duplicate_key(bibkeys, bibkey):
    # Check that we do not have a duplicate key
    if bibkey in bibkeys:
        i = 97
        while i < 123:
            if bibkey + chr(i) not in bibkeys:
                bibkey = bibkey + chr(i)
                break
            i += 1
        if i == 123:
            bibkey = bibkey + "_" + args.ref
    return bibkey


def main():
    args = parse_args()
    now = time.localtime()
    bdn = parse_bibtex(args)
    bibkeys = set(bdn.entries.keys())

    if not os.path.isfile(args.ref):
        if re.match('^[0-9]{4}\.[0-9]+$', args.ref) != None:
            # Match Arxiv reference

            # Check if duplicate or not
            match = find_dup_entry(bdn, "eprint", args.ref)
            if match is not None:
                logger.warn("Found previous entry with same id: {}".format(match[0]))
                return 1

            logger.info("Looking up arXiv reference '{}'...".format(args.ref))
            a = arxiv.query(id_list=[args.ref])
            if len(a) == 0:
                logger.fatal("arXiv reference '{}' not found".format(args.ref))
                return 1
            if len(a) > 1:
                logger.fatal("More than one article found for arXiv reference '{}'".format(args.ref))
                return 1
            a = a[0]
            logger.info("Found article: {}".format(a['title']))

            dp = a['published_parsed']

            bibkey = a['authors'][0].split(' ')
            bibkey = "{}{}".format(bibkey[1], dp.tm_year)
            bibkey = check_duplicate_key(bibkeys, bibkey)

            bib_data = BibliographyData({
                bibkey: Entry('Article', [
                    ('author', " and ".join(a['authors'])),
                    ('title', a['title']),
                    ('year', str(dp.tm_year)),
                    ('date', '{}-{:02d}-{:02d}'.format(dp.tm_year, dp.tm_mon, dp.tm_mday)),
                    ('eprint', args.ref),
                    ('eprintclass', a['arxiv_primary_category']['term']),
                    ('eprinttype', 'arXiv'),
                    ('keywords', ", ".join(map(lambda x: x['term'], a['tags']))),
                    ('timestamp', args.timestamp_format.format(now.tm_year, now.tm_mon, now.tm_mday)),
                ]),
            })
            e = bib_data.entries[bibkey]
            write_full_entry = True

            if args.dryrun:
                pdf = re.sub(r"[^\w_\- ]", "", a['title'])
                pdf = os.path.join('/tmp', pdf) + '.pdf'
            else:
                pdf = arxiv.download(a, dirpath='/tmp/')
            logger.info("Downloaded PDF to: {}".format(pdf))


        elif re.match('^[0-9\.]+/.+', args.ref) != None:
            # Match DOI

            # Check if duplicate or not
            match = find_dup_entry(bdn, "doi", args.ref)
            if match is not None:
                logger.warn("Found previous entry with same DOI: {}".format(match[0]))
                return 1

            # Search with crossref
            try:
                bib_item = cn.content_negotiation(args.ref, format="bibtex")
            except:
                # TODO: Check for 404 error
                print("Unable to find DOI")
                sys.exit(1)
            bib_data = parse_bibtex_string(bib_item, "bibtex")
            ein = bib_data.entries.values()[0]
            print("Found article: {}".format(ein.fields["title"]))

            # Remove unnecessary fields from the bibtex file
            fields = [('timestamp', args.timestamp_format.format(now.tm_year, now.tm_mon, now.tm_mday))]
            for k, v in ein.fields.items():
                if k == "url":
                    continue
                fields.append((k, v))

            e = Entry(ein.type, fields=fields, persons=ein.persons)
            bibkey = "{}{}".format("".join(e.persons["author"][0].last()), e.fields["year"])
            bibkey = check_duplicate_key(bibkeys, bibkey)
            bib_data = BibliographyData({bibkey: e})

            write_full_entry = True
            pdf = None

        else:
            logger.fatal("File '%s' not found" % args.ref)
            return 1

    else:
        pdf = args.ref
        e = find_bibentry(args, bdn)
        if e is None:
            return 1
        write_full_entry = False

    if not args.overwrite and "file" in e.fields:
        logger.error("File already defined for entry '%s'. Use '-o' option for overwritting." % e.key)
        return 1

    if pdf:
        if args.disable_rename:
            dstfname = os.path.basename(pdf)
        else:
            dstfname = re.sub(r"[^\w_\- ]", "", args.pdfformat % {**e.fields, **{'ID': e.key}})
            dstfname += os.path.splitext(pdf)[1]

        dstpath = os.path.join(args.pdfsdir, dstfname)
        if not os.path.exists(dstpath):
            logger.info(u"%s → %s" % (pdf, dstpath))
            if not args.dryrun:
                shutil.move(pdf, dstpath)
        elif not os.path.samefile(pdf, dstpath):
            logger.error("File already existing at %s" % dstpath)
            return 1

        ext = os.path.splitext(pdf)[1][1:].upper()
        e.fields["file"] = ":%s:%s" % (dstfname, ext)

        fline = "file = {%s}," % e.fields["file"]
        if write_full_entry:
            print(bib_data.to_string('bibtex'))
        else:
            print(fline)

    if args.dryrun:
        return 0

    if write_full_entry:
        with codecs.open(args.bibfile, "r", "utf-8") as f:
            lines = f.readlines()

        wrote_entry = False
        bibfile_tmp = args.bibfile + ".tmp"
        with codecs.open(bibfile_tmp, "w", "utf-8") as f:
            for l in lines:
                # JabRef adds comments at the end of the bibtex file
                if not wrote_entry and l.startswith('@Comment'):
                    f.write(bib_data.to_string('bibtex'))
                    f.write("\n")
                    wrote_entry = True

                f.write(l)

            if not wrote_entry:
                f.write(bib_data.to_string('bibtex'))

        shutil.move(bibfile_tmp, args.bibfile)
        return 0

    else:
        klook = "@%s{%s," % (e.type, e.key)
        klook = klook.lower()

        with codecs.open(args.bibfile, "r", "utf-8") as f:
            lines = f.readlines()

        wrote_fline = False
        bibfile_tmp = args.bibfile + ".tmp"
        with codecs.open(bibfile_tmp, "w", "utf-8") as f:
            for l in lines:
                f.write(l)
                if not wrote_fline and l.lower().find(klook) != -1:
                    logger.info('Writting file in entry')
                    f.write("  " + fline + "\n")
                    wrote_fline = True

        if not wrote_fline:
            logger.error("Couldn't find where to write the file entry!")
            os.remove(bibfile_tmp)
            # Rollback
            logger.info(u"Rollback: %s → %s" % (dstpath, pdf))
            shutil.move(dstpath, pdf)
            return 1

        shutil.move(bibfile_tmp, args.bibfile)
        return 0


if __name__ == "__main__":
    main()
