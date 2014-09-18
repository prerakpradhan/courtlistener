from tastypie.api import Api
from django.conf.urls import include, patterns, url
from django.contrib import admin
from django.views.generic import RedirectView

from alert.alerts.views import delete_alert, delete_alert_confirm, \
    edit_alert_redirect
from alert.api.views import (
    court_index, documentation_index, dump_index, rest_index,
    serve_or_gen_dump, serve_pagerank_file)
from alert.audio.feeds import AllJurisdictionsPodcast, JurisdictionPodcast, \
    SearchPodcast
from alert.audio.views import view_audio_file
from alert.AuthenticationBackend import ConfirmedEmailAuthenticationForm
from alert.casepage.sitemap import sitemap_maker, flat_sitemap_maker
from alert.casepage.views import (
    view_opinion, view_opinion_citations, view_authorities, view_docket,
    serve_static_file, redirect_opinion_pages)
from alert.citations.feeds import CitedByFeed
from alert.donate.dwolla import process_dwolla_callback, \
    process_dwolla_transaction_status_callback
from alert.donate.paypal import process_paypal_callback, donate_paypal_cancel
from alert.donate.sitemap import donate_sitemap_maker
from alert.donate.stripe_helpers import process_stripe_callback
from alert.donate.views import view_donations, donate, donate_complete
from alert.favorites.views import delete_favorite, edit_favorite, \
    save_or_update_favorite
from alert.search import api
from alert.search import api2
from alert.search.feeds import SearchFeed, JurisdictionFeed, \
    AllJurisdictionsFeed
from alert.search.models import Court
from alert.search.views import browser_warning, show_results, tools_page
from alert.simple_pages.api import coverage_data
from alert.userHandling.views import (
    confirmEmail, deleteProfile, deleteProfileDone, emailConfirmSuccess,
    password_change, register, register_success,
    request_email_confirmation, view_favorites, view_alerts, view_settings)


# for the flatfiles in the sitemap
from django.contrib.auth.views import (
    login as signIn, logout as signOut, password_reset,
    password_reset_done, password_reset_confirm
)


pacer_codes = Court.objects.filter(in_use=True).values_list('pk', flat=True)
mime_types = ('pdf', 'wpd', 'txt', 'doc', 'html')

# Set up the API
v1_api = Api(api_name='v1')
v1_api.register(api.CitationResource(tally_name='search.api.citation'))
v1_api.register(api.CourtResource(tally_name='search.api.court'))
v1_api.register(api.DocumentResource(tally_name='search.api.document'))
v1_api.register(api.SearchResource(tally_name='search.api.search'))
v1_api.register(api.CitesResource(tally_name='search.api.cites'))
v1_api.register(api.CitedByResource(tally_name='search.api.cited-by'))
v2_api = Api(api_name='v2')
v2_api.register(api2.CitationResource(tally_name='search.api2.citation'))
v2_api.register(api2.CourtResource(tally_name='search.api2.court'))
v2_api.register(api2.DocumentResource(tally_name='search.api2.document'))
v2_api.register(api2.SearchResource(tally_name='search.api2.search'))
v2_api.register(api2.CitesResource(tally_name='search.api2.cites'))
v2_api.register(api2.CitedByResource(tally_name='search.api2.cited-by'))

# enables the admin (must be last due to autodiscover performing imports from all apps):
admin.autodiscover()

urlpatterns = patterns('',
    # Admin docs and site
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),

    # favicon and apple touch icons (needed in urls.py because they have to be at the root)
    (r'^favicon\.ico$',
     RedirectView.as_view(url='/static/ico/favicon.ico', permanent=True)),
    (r'^apple-touch-icon\.png$',
     RedirectView.as_view(url='/static/png/apple-touch-icon.png', permanent=True)),
    (r'^apple-touch-icon-57x57-precomposed\.png$',
     RedirectView.as_view(url='/static/png/apple-touch-icon-57x57-precomposed.png', permanent=True)),
    (r'^apple-touch-icon-72x72-precomposed\.png$',
     RedirectView.as_view(url='/static/png/apple-touch-icon-72x72-precomposed.png', permanent=True)),
    (r'^apple-touch-icon-114x114-precomposed\.png$',
     RedirectView.as_view(url='/static/png/apple-touch-icon-114x114-precomposed.png', permanent=True)),
    (r'^apple-touch-icon-precomposed\.png$',
     RedirectView.as_view(url='/static/png/apple-touch-icon-precomposed.png', permanent=True)),
    (r'^bad-browser/$', browser_warning),

    # Maintenance and SOPA/PIPA mode!
    #(r'/*', show_maintenance_warning),

    # An opinion, authorities and cited-by/
    url(r'^opinion/(\d*)/(.*)/cited-by/$', view_opinion_citations, name='view_case_citations'),
    url(r'^opinion/(\d*)/(.*)/authorities/$', view_authorities, name='view_authorities'),
    url(r'^opinion/(\d*)/(.*)/$', view_opinion, name="view_case"),
    url(r'^docket/(\d*)/(.*)/$', view_docket, name="view_docket"),
    url(r'^audio/(\d*)/(.*)/$', view_audio_file, name="view_audio_file"),

    # Serve a static file
    (r'^(?P<file_path>(?:' + "|".join(mime_types) + ')/.*)$',
        serve_static_file),

    # Simple pages
    url('^', include('alert.simple_pages.urls')),

    # Various sign in/out etc. functions as provided by django
    url(
        r'^sign-in/$',
        signIn,
        {'authentication_form': ConfirmedEmailAuthenticationForm, 'extra_context': {'private': False}},
        name="sign-in"
    ),
    (r'^sign-out/$', signOut, {'extra_context': {'private': False}}),

    # Settings pages
    url(r'^profile/settings/$', view_settings, name='view_settings'),
    (r'^profile/$', RedirectView.as_view(url='/profile/settings/', permanent=True)),
    (r'^profile/favorites/$', view_favorites),
    (r'^profile/alerts/$', view_alerts),
    (r'^profile/donations/$', view_donations),
    (r'^profile/password/change/$', password_change),
    (r'^profile/delete/$', deleteProfile),
    (r'^profile/delete/done/$', deleteProfileDone),
    url(r'^register/$', register, name="register"),
    (r'^register/success/$', register_success),

    # Favorites pages
    (r'^favorite/create-or-update/$', save_or_update_favorite),
    (r'^favorite/delete/$', delete_favorite),
    (r'^favorite/edit/(\d{1,6})/$', edit_favorite),

    # Registration pages
    (r'^email/confirm/([0-9a-f]{40})/$', confirmEmail),
    (r'^email-confirmation/request/$', request_email_confirmation),
    (r'^email-confirmation/success/$', emailConfirmSuccess),

    # Reset password pages
    (r'^reset-password/$', password_reset, {'extra_context': {'private': False}}),
    (r'^reset-password/instructions-sent/$', password_reset_done, {'extra_context': {'private': False}}),
    (r'^confirm-password/(?P<uidb36>.*)/(?P<token>.*)/$', password_reset_confirm,
     {'post_reset_redirect': '/reset-password/complete/', 'extra_context': {'private': False}}),
    (r'^reset-password/complete/$', signIn, {'template_name': 'registration/password_reset_complete.html',
                                             'extra_context': {'private': False}}),

    # Search pages
    (r'^$', show_results),  # the home page!

    # Alert pages
    (r'^alert/edit/(\d{1,6})/$', edit_alert_redirect),
    (r'^alert/delete/(\d{1,6})/$', delete_alert),
    (r'^alert/delete/confirm/(\d{1,6})/$', delete_alert_confirm),
    (r'^tools/$', tools_page),

    # The API
    (r'^api/$', documentation_index),
    (r'^api/jurisdictions/$', court_index),
    (r'^api/rest/v[12]/coverage/(all|%s)/' % '|'.join(pacer_codes), coverage_data),
    (r'^api/rest/', include(v1_api.urls)),
    (r'^api/rest/', include(v2_api.urls)),
    (r'^api/rest-info/$', rest_index),
    (r'^api/bulk-info/$', dump_index),
    (r'^api/bulk/(?P<court>all|%s)\.xml\.gz$' % "|".join(pacer_codes),
        serve_or_gen_dump),
    (r'^api/bulk/(?P<year>\d{4})/(?P<court>all|%s)\.xml\.gz$' % "|".join(pacer_codes),
        serve_or_gen_dump),
    (r'^api/bulk/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<court>all|%s)\.xml\.gz$' % "|".join(pacer_codes),
        serve_or_gen_dump),
    (r'^api/bulk/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<court>all|%s)\.xml\.gz$' % "|".join(pacer_codes),
        serve_or_gen_dump),
    (r'^api/bulk/external_pagerank/$', serve_pagerank_file),

    # Feeds & podcasts
    (r'^feed/(search)/$', SearchFeed()),  # lacks URL capturing b/c it will use GET queries.
    (r'^feed/court/all/$', AllJurisdictionsFeed()),
    (r'^feed/court/(?P<court>' + '|'.join(pacer_codes) + ')/$', JurisdictionFeed()),
    (r'^feed/(?P<doc_id>.*)/cited-by/$', CitedByFeed()),
    (r'^podcast/court/(?P<court>' + '|'.join(pacer_codes) + ')/$', JurisdictionPodcast()),
    (r'^podcast/court/all/$', AllJurisdictionsPodcast()),
    (r'^podcast/(search)/', SearchPodcast()),

    # Sitemaps
    (r'^sitemap\.xml$', sitemap_maker),
    (r'^sitemap-flat\.xml$', flat_sitemap_maker),
    (r'^sitemap-donate\.xml$', donate_sitemap_maker),

    # Donations
    (r'^donate/$', donate),
    (r'^donate/dwolla/complete/$', donate_complete),
    (r'^donate/paypal/complete/$', donate_complete),
    (r'^donate/stripe/complete/$', donate_complete),
    (r'^donate/callbacks/dwolla/$', process_dwolla_callback),
    (r'^donate/callbacks/dwolla/transaction-status/$', process_dwolla_transaction_status_callback),
    (r'^donate/callbacks/paypal/$', process_paypal_callback),
    (r'^donate/callbacks/stripe/$', process_stripe_callback),
    (r'^donate/paypal/cancel/$', donate_paypal_cancel),
)

urlpatterns += patterns(
    (r'^privacy/$', RedirectView.as_view(url='/terms/#privacy')),
    (r'^removal/$', RedirectView.as_view(url='/terms/#removal')),
    (r'^report/2010/$', RedirectView.as_view(
        url='https://www.ischool.berkeley.edu/files/student_projects/Final_Report_Michael_Lissner_2010-05-07_2.pdf')),
    (r'^report/2012/$', RedirectView.as_view(
        url='https://www.ischool.berkeley.edu/files/student_projects/mcdonald_rustad_report.pdf')),

    # Dump URLs changed 2013-11-07
    (r'^dump-info/$', RedirectView.as_view(url='/api/bulk-info/')),
    (r'^dump-api/(?P<court>all|%s)\.xml.gz$' % "|".join(pacer_codes),
     RedirectView.as_view(url='/api/bulk/%(court)s.xml.gz')),
    (r'^dump-api/(?P<year>\d{4})/(?P<court>all|%s)\.xml.gz$' % "|".join(pacer_codes),
     RedirectView.as_view(url='/api/bulk/%(year)s/%(court)s.xml.gz')),
    (r'^dump-api/(?P<year>\d{4})/(?P<month>\d{2})/(?P<court>all|%s)\.xml.gz$' % "|".join(pacer_codes),
     RedirectView.as_view(url='/api/bulk/%(year)s/%(month)s/%(court)s.xml.gz')),
    (r'^dump-api/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<court>all|%s)\.xml.gz$' % "|".join(pacer_codes),
     RedirectView.as_view(url='/api/bulk/%(year)s/%(month)s/%(day)s/%(court)s.xml.gz')),

    # Court stripped from the URL on 2014-06-26
    (r'^(?:%s)/(.*)/(.*)/authorities/$' % "|".join(pacer_codes), redirect_opinion_pages),
    (r'^(?:%s)/(.*)/(.*)/cited-by/$' % "|".join(pacer_codes), redirect_opinion_pages),
    (r'^(?:%s)/(.*)/(.*)/$' % "|".join(pacer_codes), redirect_opinion_pages),
)
