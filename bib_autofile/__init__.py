#/usr/bin/env python3
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


def get_bibkeys(args):
    parser = bibtex.Parser()
    with codecs.open(args.bibfile, "r", "utf-8") as fhandle:
        bdn = parser.parse_file(fhandle)
    return set(bdn.entries.keys())

def find_bibentry(args):
    parser = bibtex.Parser()
    with codecs.open(args.bibfile, "r", "utf-8") as fhandle:
        bdn = parser.parse_file(fhandle)

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


def main(args):
    if not os.path.isfile(args.ref):
        if re.match('^[0-9]{4}\.[0-9]+$', args.ref) != None:
            logger.info("Looking up arxiv reference {}...".format(args.ref))
            a = arxiv.query(id_list=[args.ref])
            if len(a) != 1:
                logger.fatal("Arxiv reference '{}' not found".format(args.ref))
                return 1
            a = a[0]

            dp = a['published_parsed']
            now = time.localtime()

            bibkey = a['authors'][0].split(' ')
            bibkey = "{}{}".format(bibkey[1], dp.tm_year)
            # Check that we do not have a duplicate key
            bibkeys = get_bibkeys(args)
            if bibkey in bibkeys:
                i = 97
                while i < 123:
                    if bibkey + chr(i) not in bibkeys:
                        bibkey = bibkey + chr(i)
                        break
                    i += 1
                if i == 123:
                    bibkey = bibkey + "_" + args.ref

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
                pdf = arxiv.download(a, dirname='/tmp/')
            logger.info("Downloaded PDF to: {}".format(pdf))

        else:
            logger.fatal("File '%s' not found" % args.ref)
            return 1

    else:
        pdf = args.ref
        e = find_bibentry(args)
        if e is None:
            return 1
        write_full_entry = False

    if not args.overwrite and "file" in e.fields:
        logger.error("File already defined for entry '%s'. Use '-o' option for overwritting." % e.key)
        return 1

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
    args = parse_args()
    main(args)
