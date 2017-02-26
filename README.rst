============
bib_autofile
============

``bib_autofile`` is a small script to automatically set the ``file`` key in a bibtex entry using a given PDF file

Installation
============

From Github:

.. code-block:: shell

    $ pip install --upgrade https://github.com/fg1/bib_autofile/archive/master.tar.gz

Usage
=====

.. code-block:: shell

    usage: __init__.py [-h] [-k BIBKEY] [--bibfile BIBFILE] [--pdfsdir PDFSDIR]
                       [--pdfformat PDFFORMAT] [-o] [-r] [-d]
                       pdf

    positional arguments:
      pdf
    
    optional arguments:
      -h, --help            show this help message and exit
      -k BIBKEY
      --bibfile BIBFILE     Bibliography file
      --pdfsdir PDFSDIR     Directory with PDFs
      --pdfformat PDFFORMAT
                            Which format should be used for the name of the PDF
      -o                    Overwrites the file in the bibtex entry
      -r                    Disable renaming of the PDF file
      -d                    Do not perform actions

