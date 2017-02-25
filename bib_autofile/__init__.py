#/usr/bin/python
# coding: utf-8

# TODO:
#  - Find the bib key using XMP data (exiftool -a -G1 xxx.pdf)

from __future__ import print_function

import os
import re
import sys
import codecs
import shutil
import logging

import bibtexparser
from clint import resources
from clint.textui import prompt
import configargparse as argparse

resources.init("fg1", "bib_autofile")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def parse_args():
    parser = argparse.ArgumentParser(description="bibtex helper", default_config_files=[os.path.join(resources.user.path, "config.ini")])
    parser.add_argument("pdf", type=str)
    parser.add_argument("-k", dest="bibkey", default="last", type=str)
    parser.add_argument("--bibfile", help="Bibliography file", type=str)
    parser.add_argument("--pdfsdir", help="Directory with PDFs", type=str)
    parser.add_argument("--pdfformat", help="Which format should be used for the name of the PDF", default="%(ID)s - %(title)s", type=str)
    parser.add_argument("-o", dest="overwrite", action="store_true", help="Overwrites the file in the bibtex entry")
    parser.add_argument("-r", dest="disable_rename", action="store_true", help="Disable renaming of the PDF file")
    parser.add_argument("-d", dest="dryrun", action="store_true", help="Do not perform actions")
    return parser.parse_args()


def find_bibentry(args):
    parser = bibtexparser.bparser.BibTexParser()
    parser.ignore_nonstandard_types = False
    parser.customization = bibtexparser.customization.convert_to_unicode

    with codecs.open(args.bibfile, "r", "utf-8") as fhandle:
        bdn = bibtexparser.load(fhandle, parser=parser)

        if args.bibkey == "last":
            s = sorted(bdn.entries, key=lambda e: (e["timestamp"], e["ID"]), reverse=True)
            if not args.overwrite:
                s = filter(lambda e: "file" not in e, s)
            ltstamp = s[0]["timestamp"]
            s = filter(lambda e: e["timestamp"] == ltstamp, s)

            if len(s) == 1:
                vars(args)["bibkey"] = s[0]["ID"]
            else:
                choices = []
                i = 0
                for e in s:
                    choices.append({"selector": i, "prompt": "%s - %s" % (e["ID"], e["title"]), "return": e["ID"]})
                    i += 1
                vars(args)["bibkey"] = prompt.options("Which entry?", choices)

        # Check that the key which is specified exists
        if args.bibkey not in bdn.entries_dict:
            logger.fatal("Couldn't find key '%s' in bibtex file" % args.bibkey)
            return None
        return bdn.entries_dict[args.bibkey]


def main():
    args = parse_args()

    if not os.path.isfile(args.pdf):
        logger.fatal("File '%s' not found" % args.pdf)
        return 1

    e = find_bibentry(args)
    if e is None:
        return 1

    if not args.overwrite and "file" in e:
        logger.error("File already defined for entry '%s'. Use '-o' option for overwritting." % args.bibkey)
        return 1

    if args.disable_rename:
        dstfname = os.path.basename(args.pdf)
    else:
        dstfname = re.sub(r"[^\w_\- ]", "", args.pdfformat % e)
        dstfname += os.path.splitext(args.pdf)[1]

    dstpath = os.path.join(args.pdfsdir, dstfname)
    if not os.path.exists(dstpath):
        logger.info(u"%s → %s" % (args.pdf, dstpath))
        if not args.dryrun:
            shutil.move(args.pdf, dstpath)
    elif not os.path.samefile(args.pdf, dstpath):
        logger.error("File already existing at %s" % dstpath)
        return 1

    ext = os.path.splitext(args.pdf)[1][1:].upper()
    e["file"] = ":%s:%s" % (dstfname, ext)

    fline = "file = {%s}," % e["file"]
    print(fline)
    if args.dryrun:
        return 0

    klook = "@%s{%s," % (e["ENTRYTYPE"], e["ID"])
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
        return 1

    shutil.move(bibfile_tmp, args.bibfile)
    return 0


if __name__ == "__main__":
    main()
