from alert.lib import sunburnt
from alert.search.models import Citation, Court, Document
from alert.scrapers.test_assets import test_scraper
from django.test import TestCase
from django.test.client import Client

from alert import settings


class SetupException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


def clear_solr(si):
    # Clear the Solr index
    response = si.raw_query(**{'q': '*:*'}).execute()
    count = response.result.numFound
    if 0 < count <= 10000:
        si.delete_all()
        si.commit()
    elif count > 10000:
        raise SetupException('Solr has more than 10000 items. Will not empty as part of a test.')


class SearchTest(TestCase):
    fixtures = ['test_court.json']

    def setUp(self):
        # Set up some handy variables
        self.court = Court.objects.get(pk='test')
        self.client = Client()
        self.si = sunburnt.SolrInterface(settings.SOLR_URL, mode='rw')

        # Clear Solr
        clear_solr(self.si)

        # Add two documents to the index, but don't extract their contents
        self.site = test_scraper.Site().parse()
        cite_counts = (4, 6)
        for i in range(0, 1):
            cite = Citation(case_name=self.site.case_names[i],
                            docket_number=self.site.docket_numbers[i],
                            neutral_cite=self.site.neutral_citations[i],
                            west_cite=self.site.west_citations[i])
            cite.save(index=False)
            self.doc = Document(date_filed=self.site.case_dates[i],
                                court=self.court,
                                citation=cite,
                                precedential_status=self.site.precedential_statuses[i],
                                citation_count=cite_counts[i])
            self.doc.save()

    def tearDown(self):
        self.doc.delete()

        clear_solr(self.si)

    def test_a_simple_text_query(self):
        """Does typing into the main query box work?"""
        response = self.client.get('/', {'q': 'supreme'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)

    def test_a_case_name_query(self):
        """Does querying by case name work?"""
        response = self.client.get('/', {'q': '*:*', 'case_name': 'tarrant'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)

    def test_a_query_with_a_date(self):
        """Does querying by date work?"""
        response = self.client.get('/', {'q': '*:*',
                                         'filed_after': '2013-06',
                                         'filed_before': '2013-07'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)

    def test_faceted_queries(self):
        """Does querying in a given court return the document? Does querying the wrong facets exclude it?"""
        response = self.client.get('/', {'q': '*:*', 'court_test': 'on'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)
        response = self.client.get('/', {'q': '*:*', 'stat_Errata': 'on'})
        self.assertNotIn('Tarrant Regional Water District',
                         response.content)

    def test_a_docket_number_query(self):
        """Can we query by docket number?"""
        response = self.client.get('/', {'q': '*:*', 'docket_number': '11-889'})
        self.assertIn('Tarrant Regional Water District',
                      response.content, "Result not found by docket number!")

    def test_a_west_citation_query(self):
        """Can we query by citation number?"""
        get_dicts = [{'q': '*:*', 'west_cite': '44'},
                     {'q': 'westCite:44'},
                     {'q': 'westcite:44'}]  # Tests query field lower-casing
        for get_dict in get_dicts:
            response = self.client.get('/', get_dict)
            self.assertIn('Tarrant Regional Water District',
                          response.content)

    def test_a_neutral_citation_query(self):
        """Can we query by neutral citation numbers?"""
        response = self.client.get('/', {'q': '*:*', 'neutral_cite': '44'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)

    def test_a_query_with_a_old_date(self):
        """Do we have any recurrent issues with old dates and strftime (issue 220)?"""
        response = self.client.get('/', {'q': '*:*',
                                         'filed_after': '1890'})
        self.assertEqual(200, response.status_code)

    def test_a_judge_query(self):
        """Can we query by judge name?"""
        response = self.client.get('/', {'q': '*:*', 'judge': 'david'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)
        response = self.client.get('/', {'q': 'judge:david'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)

    def test_a_nature_of_suit_query(self):
        """Can we query by nature of suit?"""
        response = self.client.get('/', {'q': 'suitNature:copyright'})
        self.assertIn('Tarrant Regional Water District',
                      response.content)

    def test_citation_filtering(self):
        """Can we find Documents by citation filtering?"""
        msg = "%s case back when filtering by citation count."
        response = self.client.get('/', {'q': '*:*', 'citeCount_lt': 5, 'citeCount_gt': 3})
        self.assertIn('Tarrant Regional Water District',
                      response.content, msg=msg % 'Did not get')
        response = self.client.get('/', {'q': '*:*', 'citeCount_lt': 10, 'citeCount_gt': 8})
        self.assertNotIn('Tarrant Regional Water District',
                         response.content, msg=msg % 'Got')

    def test_citation_ordering(self):
        """Can the results be re-ordered by citation count?"""
        response = self.client.get('/', {'q': '*:*', 'sort': 'citeCount desc'})
        self.assertTrue(response.content.index('Disclosure') < response.content.index('Tarrant'),
                        msg="'Disclosure' should come BEFORE 'Tarrant' when ordered by descending citeCount.")
        response = self.client.content.get('/', {'q': '*:*', 'sort': 'citeCount asc'})
        self.assertTrue(response.index('Disclosure') > response.content.index('Tarrant'),
                        msg="'Disclosure' should come AFTER 'Tarrant' when ordered by ascending citeCount.")
