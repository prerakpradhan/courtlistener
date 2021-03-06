#!/usr/bin/env python

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'alert.settings'

import sys
# append these to the path to make the dev machines and the server happy (respectively)
execfile('/etc/courtlistener')
sys.path.append(INSTALL_ROOT)

from django import db
from django.core.exceptions import MultipleObjectsReturned
from django.utils.text import slugify
from alert.search.models import Court, Document
from alert.lib.parse_dates import parse_dates
from juriscraper.lib.string_utils import trunc
from alert.lib.scrape_tools import hasDuplicate

from lxml.html import fromstring, tostring
from urlparse import urljoin
import datetime
import re
import subprocess
import time
import urllib2


def load_fix_files():
    """Loads the fix files into memory so they can be accessed efficiently."""
    court_fix_file = open('../logs/f2_court_fix_file.txt', 'r')
    date_fix_file = open('../logs/f2_date_fix_file.txt', 'r')
    case_name_short_fix_file = open('../logs/f2_short_case_name_fix_file.txt', 'r')
    court_fix_dict = {}
    date_fix_dict = {}
    case_name_short_dict = {}
    for line in court_fix_file:
        key, value = line.split('|')
        court_fix_dict[key] = value
    for line in date_fix_file:
        key, value = line.split('|')
        date_fix_dict[key] = value
    for line in case_name_short_fix_file:
        key, value = line.split('|')
        case_name_short_dict[key] = value

    court_fix_file.close()
    date_fix_file.close()
    case_name_short_fix_file.close()
    return court_fix_dict, date_fix_dict, case_name_short_dict


def check_fix_list(sha1, fix_dict):
    """ Given a sha1, return the correction for a case. Return false if no values.

    Corrections are strings that the parser can interpret as needed. Items are
    written to this file the first time the cases are imported, and this file
    can be used to import F2 into later systems.
    """
    try:
        return fix_dict[sha1].strip()
    except KeyError:
        return False


def exceptional_cleaner(caseName):
    """Cleans common Resource.org special cases off of case names, and
    sets the precedential_status for a document.

    Returns caseName, precedential_status
    """
    caseName = caseName.lower()
    ca1regex = re.compile('(unpublished disposition )?notice: first circuit local rule 36.2\(b\)6 states unpublished opinions may be cited only in related cases.?')
    ca2regex = re.compile('(unpublished disposition )?notice: second circuit local rule 0.23 states unreported opinions shall not be cited or otherwise used in unrelated cases.?')
    ca3regex = re.compile('(unpublished disposition )?notice: third circuit rule 21\(i\) states citations to federal decisions which have not been formally reported should identify the court, docket number and date.?')
    ca4regex = re.compile('(unpublished disposition )?notice: fourth circuit (local rule 36\(c\)|i.o.p. 36.6) states that citation of unpublished dispositions is disfavored except for establishing res judicata, estoppel, or the law of the case and requires service of copies of cited unpublished dispositions of the fourth circuit.?')
    ca5regex = re.compile('(unpublished disposition )?notice: fifth circuit local rule 47.5.3 states that unpublished opinions should normally be cited only when they establish the law of the case, are relied upon as a basis for res judicata or collateral estoppel, or involve related facts. if an unpublished opinion is cited, a copy shall be attached to each copy of the brief.?')
    ca6regex = re.compile('(unpublished disposition )?notice: sixth circuit rule 24\(c\) states that citation of unpublished dispositions is disfavored except for establishing res judicata, estoppel, or the law of the case and requires service of copies of cited unpublished dispositions of the sixth circuit.?')
    ca7regex = re.compile('(unpublished disposition )?notice: seventh circuit rule 53\(b\)\(2\) states unpublished orders shall not be cited or used as precedent except to support a claim of res judicata, collateral estoppel or law of the case in any federal court within the circuit.?')
    ca8regex = re.compile('(unpublished disposition )?notice: eighth circuit rule 28a\(k\) governs citation of unpublished opinions and provides that (no party may cite an opinion not intended for publication unless the cases are related by identity between the parties or the causes of action|they are not precedent and generally should not be cited unless relevant to establishing the doctrines of res judicata, collateral estoppel, the law of the case, or if the opinion has persuasive value on a material issue and no published opinion would serve as well).?')
    ca9regex = re.compile('(unpublished disposition )?notice: ninth circuit rule 36-3 provides that dispositions other than opinions or orders designated for publication are not precedential and should not be cited except when relevant under the doctrines of law of the case, res judicata, or collateral estoppel.?')
    ca10regex = re.compile('(unpublished disposition )?notice: tenth circuit rule 36.3 states that unpublished opinions and orders and judgments have no precedential value and shall not be cited except for purposes of establishing the doctrines of the law of the case, res judicata, or collateral estoppel.?')
    cadcregex = re.compile('(unpublished disposition )?notice: d.c. circuit local rule 11\(c\) states that unpublished orders, judgments, and explanatory memoranda may not be cited as precedents, but counsel may refer to unpublished dispositions when the binding or preclusive effect of the disposition, rather than its quality as precedent, is relevant.?')
    cafcregex = re.compile('(unpublished disposition )?notice: federal circuit local rule 47.(6|8)\(b\) states that opinions and orders which are designated as not citable as precedent shall not be employed or cited as precedent. this does not preclude assertion of issues of claim preclusion, issue preclusion, judicial estoppel, law of the case or the like based on a decision of the court rendered in a nonprecedential opinion or order.?')
    # Clean off special cases
    if 'first circuit' in caseName:
        caseName = re.sub(ca1regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'second circuit' in caseName:
        caseName = re.sub(ca2regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'third circuit' in caseName:
        caseName = re.sub(ca3regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'fourth circuit' in caseName:
        caseName = re.sub(ca4regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'fifth circuit' in caseName:
        caseName = re.sub(ca5regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'sixth circuit' in caseName:
        caseName = re.sub(ca6regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'seventh circuit' in caseName:
        caseName = re.sub(ca7regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'eighth circuit' in caseName:
        caseName = re.sub(ca8regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'ninth circuit' in caseName:
        caseName = re.sub(ca9regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'tenth circuit' in caseName:
        caseName = re.sub(ca10regex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'd.c. circuit' in caseName:
        caseName = re.sub(cadcregex, '', caseName)
        precedential_status = 'Unpublished'
    elif 'federal circuit' in caseName:
        caseName = re.sub(cafcregex, '', caseName)
        precedential_status = 'Unpublished'
    else:
        precedential_status = 'Published'

    return caseName, precedential_status


def scrape_and_parse():
    """Traverses the bulk data from public.resource.org, and puts them in the
    DB.

    Probably lots of ways to go about this, but I think the easiest will be the following:
     - look at the index page of all volumes, and follow all the links it has.
     - for each volume, look at its index page, and follow the link to all cases
     - for each case, collect information wisely.
     - put it all in the DB
    """

    # begin by loading up the fix files into memory
    court_fix_dict, date_fix_dict, case_name_short_dict = load_fix_files()

    results = []
    DEBUG = 4
    # Set to False to disable automatic browser usage. Else, set to the
    # command you want to run, e.g. 'firefox'
    BROWSER = False
    court_fix_file = open('../logs/f2_court_fix_file.txt', 'a')
    date_fix_file = open('../logs/f2_date_fix_file.txt', 'a')
    case_name_short_fix_file = open('../logs/f2_short_case_name_fix_file.txt', 'a')
    vol_file = open('../logs/vol_file.txt', 'r+')
    case_file = open('../logs/case_file.txt', 'r+')

    url = "file://%s/Resource.org/F2/index.html" % INSTALL_ROOT
    openedURL = urllib2.urlopen(url)
    content = openedURL.read()
    openedURL.close()
    tree = fromstring(content)

    volumeLinks = tree.xpath('//table/tbody/tr/td[1]/a')

    try:
        i = int(vol_file.readline())
    except ValueError:
        # the volume file is emtpy or otherwise failing.
        i = 0
    vol_file.close()

    if DEBUG >= 1:
        print "Number of remaining volumes is: %d" % (len(volumeLinks) - i)

    # used later, needs a default value.
    saved_caseDate = None
    saved_court = None
    while i < len(volumeLinks):
        # we iterate over every case in the volume
        volumeURL = volumeLinks[i].text + "/index.html"
        volumeURL = urljoin(url, volumeURL)
        if DEBUG >= 1:
            print "Current volumeURL is: %s" % volumeURL

        openedVolumeURL = urllib2.urlopen(volumeURL)
        content = openedVolumeURL.read()
        volumeTree = fromstring(content)
        openedVolumeURL.close()
        caseLinks = volumeTree.xpath('//table/tbody/tr/td[1]/a')
        caseDates = volumeTree.xpath('//table/tbody/tr/td[2]')
        sha1Hashes = volumeTree.xpath('//table/tbody/tr/td[3]/a')

        # The following loads a serialized placeholder from disk.
        try:
            j = int(case_file.readline())
        except ValueError:
            j = 0
        case_file.close()
        while j < len(caseLinks):
            # iterate over each case, throwing it in the DB
            if DEBUG >= 1:
                print ''
            # like the scraper, we begin with the caseLink field (relative for
            # now, not absolute)
            caseLink = caseLinks[j].get('href')

            # sha1 is easy
            sha1Hash = sha1Hashes[j].text
            if DEBUG >= 4:
                print "SHA1 is: %s" % sha1Hash

            # using the caselink from above, and the volumeURL, we can get the
            # html
            absCaseLink = urljoin(volumeURL, caseLink)
            html = urllib2.urlopen(absCaseLink).read()
            htmlTree = fromstring(html)
            bodyContents = htmlTree.xpath('//body/*[not(@id="footer")]')

            body = ""
            bodyText = ""
            for element in bodyContents:
                body += tostring(element)
                try:
                    bodyText += tostring(element, method='text')
                except UnicodeEncodeError:
                    # Happens with odd characters. Simply pass this iteration.
                    pass
            if DEBUG >= 5:
                print body
                print bodyText

            # need to figure out the court ID
            try:
                courtPs = htmlTree.xpath('//p[@class = "court"]')
                # Often the court ends up in the parties field.
                partiesPs = htmlTree.xpath("//p[@class= 'parties']")
                court = ""
                for courtP in courtPs:
                    court += tostring(courtP).lower()
                for party in partiesPs:
                    court += tostring(party).lower()
            except IndexError:
                court = check_fix_list(sha1Hash, court_fix_dict)
                if not court:
                    print absCaseLink
                    if BROWSER:
                        subprocess.Popen([BROWSER, absCaseLink], shell=False).communicate()
                    court = raw_input("Please input court name (e.g. \"First Circuit of Appeals\"): ").lower()
                    court_fix_file.write("%s|%s\n" % (sha1Hash, court))
            if ('first' in court) or ('ca1' == court):
                court = 'ca1'
            elif ('second' in court) or ('ca2' == court):
                court = 'ca2'
            elif ('third' in court) or ('ca3' == court):
                court = 'ca3'
            elif ('fourth' in court) or ('ca4' == court):
                court = 'ca4'
            elif ('fifth' in court) or ('ca5' == court):
                court = 'ca5'
            elif ('sixth' in court) or ('ca6' == court):
                court = 'ca6'
            elif ('seventh' in court) or ('ca7' == court):
                court = 'ca7'
            elif ('eighth' in court) or ('ca8' == court):
                court = 'ca8'
            elif ('ninth' in court) or ('ca9' == court):
                court = 'ca9'
            elif ("tenth" in court) or ('ca10' == court):
                court = 'ca10'
            elif ("eleventh" in court) or ('ca11' == court):
                court = 'ca11'
            elif ('columbia' in court) or ('cadc' == court):
                court = 'cadc'
            elif ('federal' in court) or ('cafc' == court):
                court = 'cafc'
            elif ('patent' in court) or ('ccpa' == court):
                court = 'ccpa'
            elif (('emergency' in court) and ('temporary' not in court)) or ('eca' == court):
                court = 'eca'
            elif ('claims' in court) or ('uscfc' == court):
                court = 'uscfc'
            else:
                # No luck extracting the court name. Try the fix file.
                court = check_fix_list(sha1Hash, court_fix_dict)
                if not court:
                    # Not yet in the fix file. Check if it's a crazy ca5 case
                    court = ''
                    ca5courtPs = htmlTree.xpath('//p[@class = "center"]')
                    for ca5courtP in ca5courtPs:
                        court += tostring(ca5courtP).lower()
                    if 'fifth circuit' in court:
                        court = 'ca5'
                    else:
                        court = False

                    if not court:
                        # Still no luck. Ask for input, then append it to
                        # the fix file.
                        print absCaseLink
                        if BROWSER:
                            subprocess.Popen([BROWSER, absCaseLink], shell=False).communicate()
                        court = raw_input("Unknown court. Input the court code to proceed successfully [%s]: " % saved_court)
                        court = court or saved_court
                    court_fix_file.write("%s|%s\n" % (sha1Hash, court))

            saved_court = court
            court = Court.objects.get(pk=court)
            if DEBUG >= 4:
                print "Court is: %s" % court

            # next: west_cite, docket_number and caseName. Full casename is gotten later.
            west_cite = caseLinks[j].text
            docket_number = absCaseLink.split('.')[-2]
            caseName = caseLinks[j].get('title')

            caseName, precedential_status = exceptional_cleaner(caseName)
            cite, new = hasDuplicate(caseName, west_cite, docket_number)
            if cite.caseNameShort == '':
                # No luck getting the case name
                savedCaseNameShort = check_fix_list(sha1Hash, case_name_short_dict)
                if not savedCaseNameShort:
                    print absCaseLink
                    if BROWSER:
                        subprocess.Popen([BROWSER, absCaseLink], shell=False).communicate()
                    caseName = raw_input("Short casename: ")
                    cite.caseNameShort = trunc(caseName, 100)
                    cite.caseNameFull = caseName
                    case_name_short_fix_file.write("%s|%s\n" % (sha1Hash, caseName))
                else:
                    # We got both the values from the save files. Use 'em.
                    cite.caseNameShort = trunc(savedCaseNameShort, 100)
                    cite.caseNameFull = savedCaseNameShort

                # The slug needs to be done here, b/c it is only done automatically
                # the first time the citation is saved, and this will be
                # at least the second.
                cite.slug = trunc(slugify(cite.caseNameShort), 50)
                cite.save()

            if DEBUG >= 4:
                print "precedential_status: " + precedential_status
                print "west_cite: " + cite.west_cite
                print "caseName: " + cite.caseNameFull

            # date is kinda tricky...details here:
            # http://pleac.sourceforge.net/pleac_python/datesandtimes.html
            rawDate = caseDates[j].find('a')
            try:
                if rawDate is not None:
                    # Special cases
                    if sha1Hash == 'f0da421f117ef16223d7e61d1e4e5526036776e6':
                        date_text = 'August 28, 1980'
                    elif sha1Hash == '8cc192eaacd1c544b5e8ffbd751d9be84c311932':
                        date_text = 'August 16, 1985'
                    elif sha1Hash == 'd19bce155f72a9f981a12efabd760a35e1e7dbe7':
                        date_text = 'October 12, 1979'
                    elif sha1Hash == '9f7583cf0d46ddc9cad4e7943dd775f9e9ea99ff':
                        date_text = 'July 30, 1980'
                    elif sha1Hash == '211ea81a4ab4132483c483698d2a40f4366f5640':
                        date_text = 'November 3, 1981'
                    elif sha1Hash == 'eefb344034461e9c6912689677a32cd18381d5c2':
                        date_text = 'July 28, 1983'
                    else:
                        date_text = rawDate.text
                    try:
                        caseDate = datetime.datetime(*time.strptime(date_text, "%B, %Y")[0:5])
                    except ValueError, TypeError:
                        caseDate = datetime.datetime(*time.strptime(date_text, "%B %d, %Y")[0:5])
                else:
                    # No value was found. Throw an exception.
                    raise ValueError
            except:
                # No date provided.
                try:
                    # Try to get it from the saved list
                    caseDate = datetime.datetime(*time.strptime(check_fix_list(sha1Hash, date_fix_dict), "%B %d, %Y")[0:5])
                except:
                    caseDate = False
                if not caseDate:
                    # Parse out the dates with debug set to false.
                    try:
                        dates = parse_dates(bodyText, False)
                    except OverflowError:
                        # Happens when we try to make a date from a very large number
                        dates = []
                    try:
                        first_date_found = dates[0]
                    except IndexError:
                        # No dates found.
                        first_date_found = False
                    if first_date_found == saved_caseDate:
                        # High likelihood of date being correct. Use it.
                        caseDate = saved_caseDate
                    else:
                        print absCaseLink
                        if BROWSER:
                            subprocess.Popen([BROWSER, absCaseLink], shell=False).communicate()
                        print "Unknown date. Possible options are:"
                        try:
                            print "  1) %s" % saved_caseDate.strftime("%B %d, %Y")
                        except AttributeError:
                            # Happens on first iteration when saved_caseDate has no strftime attribute.
                            try:
                                saved_caseDate = dates[0]
                                print "  1) %s" % saved_caseDate.strftime(
                                    "%B %d, %Y")
                            except IndexError:
                                # Happens when dates has no values.
                                print "  No options available."
                        for k, date in enumerate(dates[0:4]):
                            if date.year >= 1900:
                                # strftime can't handle dates before 1900.
                                print "  %s) %s" % (k + 2,
                                                    date.strftime("%B %d, %Y"))
                        choice = raw_input("Enter the date or an option to proceed [1]: ")
                        choice = choice or 1
                        if str(choice) == '1':
                            # The user chose the default. Use the saved value from the last case
                            caseDate = saved_caseDate
                        elif choice in ['2', '3', '4', '5']:
                            # The user chose an option between 2 and 5. Use it.
                            caseDate = dates[int(choice) - 2]
                        else:
                            # The user typed a new date. Use it.
                            caseDate = datetime.datetime(*time.strptime(choice, "%B %d, %Y")[0:5])
                    date_fix_file.write("%s|%s\n" % (sha1Hash, caseDate.strftime("%B %d, %Y")))

            # Used during the next iteration as the default value
            saved_caseDate = caseDate

            if DEBUG >= 3:
                print "caseDate is: %s" % caseDate

            try:
                doc, created = Document.objects.get_or_create(
                    sha1=sha1Hash, court=court)
            except MultipleObjectsReturned:
                # this shouldn't happen now that we're using SHA1 as the dup
                # check, but the old data is problematic, so we must catch this.
                created = False

            if created:
                # we only do this if it's new
                doc.html = body
                doc.sha1 = sha1Hash
                doc.download_url = "http://bulk.resource.org/courts.gov/c/F2/"\
                    + str(i + 178) + "/" + caseLink
                doc.date_filed = caseDate
                doc.source = "R"

                doc.precedential_status = precedential_status
                doc.citation = cite
                doc.save()

            if not created:
                # something is afoot. Throw a big error.
                print "Duplicate found at volume " + str(i + 1) + \
                    " and row " + str(j + 1) + "!!!!"
                print "Found document %s in the database with doc id of %d!" % (doc, doc.pk)
                exit(1)

            # save our location within the volume.
            j += 1
            case_file = open('../logs/case_file.txt', 'w')
            case_file.write(str(j))
            case_file.close()

        # save the last volume completed.
        i += 1
        vol_file = open('../logs/vol_file.txt', 'w')
        vol_file.write(str(i))
        vol_file.close()

        # Clear query cache, as it presents a memory leak
        db.reset_queries()

    return 0

def main():
    print scrape_and_parse()
    print "Completed all volumes successfully. Exiting."
    exit(0)


if __name__ == '__main__':
    main()
