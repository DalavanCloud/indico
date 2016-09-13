# This file is part of Indico.
# Copyright (C) 2002 - 2016 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from flask import redirect, flash, jsonify

from indico.modules.events.abstracts.controllers.base import AbstractMixin
from indico.modules.events.abstracts.forms import (BOASettingsForm, AbstractSubmissionSettingsForm,
                                                   AbstractReviewingSettingsForm)
from indico.modules.events.abstracts.models.abstracts import Abstract
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractReview
from indico.modules.events.abstracts.settings import boa_settings, abstracts_settings, abstracts_reviewing_settings
from indico.modules.events.abstracts.util import AbstractListGenerator
from indico.modules.events.abstracts.views import WPManageAbstracts
from indico.util.i18n import _
from indico.web.forms.base import FormDefaults
from indico.web.util import jsonify_data, jsonify_form
from MaKaC.webinterface.rh.base import RH
from MaKaC.webinterface.rh.conferenceModif import RHConferenceModifBase


class RHManageAbstractsBase(RHConferenceModifBase):
    """Base class for all abstracts management RHs"""

    CSRF_ENABLED = True
    EVENT_FEATURE = 'abstracts'

    def _process(self):
        return RH._process(self)


class RHAbstractListBase(RHManageAbstractsBase):
    """Base class for all abstract list operations"""

    def _checkParams(self, params):
        RHManageAbstractsBase._checkParams(self, params)
        self.list_generator = AbstractListGenerator(event=self.event_new)


class RHManageAbstract(AbstractMixin, RHManageAbstractsBase):
    def _checkParams(self, params):
        RHManageAbstractsBase._checkParams(self, params)
        AbstractMixin._checkParams(self)

    def _checkProtection(self):
        RHManageAbstractsBase._checkProtection(self)
        AbstractMixin._checkProtection(self)

    def _process(self):
        return WPManageAbstracts.render_template('management/abstract.html', self._conf, abstract=self.abstract)


class RHAbstracts(RHManageAbstractsBase):
    """Display abstracts management page"""

    def _process(self):
        return WPManageAbstracts.render_template('management/abstracts.html', self._conf, event=self.event_new)


class RHManageBOA(RHManageAbstractsBase):
    """Configure book of abstracts"""

    def _process(self):
        form = BOASettingsForm(obj=FormDefaults(**boa_settings.get_all(self.event_new)))
        if form.validate_on_submit():
            boa_settings.set_multi(self.event_new, form.data)
            flash(_('Book of Abstract settings have been saved'), 'success')
            return jsonify_data()
        return jsonify_form(form)


class RHManageAbstractSubmission(RHManageAbstractsBase):
    """Configure abstract submission"""

    def _process(self):
        form = AbstractSubmissionSettingsForm(event=self.event_new,
                                              obj=FormDefaults(**abstracts_settings.get_all(self.event_new)))
        if form.validate_on_submit():
            abstracts_settings.set_multi(self.event_new, form.data)
            flash(_('Abstract submission settings have been saved'), 'success')
            return jsonify_data()
        return jsonify_form(form)


class RHManageAbstractReviewing(RHManageAbstractsBase):
    """Configure abstract reviewing"""

    def _process(self):
        has_ratings = bool(AbstractReviewRating.query
                           .join(AbstractReviewRating.review)
                           .join(AbstractReview.abstract)
                           .filter(~Abstract.is_deleted, Abstract.event_new == self.event_new)
                           .count())
        defaults = FormDefaults(abstract_review_questions=self.event_new.abstract_review_questions,
                                **abstracts_reviewing_settings.get_all(self.event_new))
        form = AbstractReviewingSettingsForm(event=self.event_new, obj=defaults, has_ratings=has_ratings)
        if form.validate_on_submit():
            data = form.data
            # XXX: we need to do this assignment for new questions,
            # but editing or deleting existing questions changes an
            # object that is already in the session so it's updated
            # in any case
            self.event_new.abstract_review_questions = data.pop('abstract_review_questions')
            abstracts_reviewing_settings.set_multi(self.event_new, data)
            flash(_('Abstract reviewing settings have been saved'), 'success')
            return jsonify_data()
        self.commit = False
        disabled_fields = form.RATING_FIELDS if has_ratings else ()
        return jsonify_form(form, disabled_fields=disabled_fields)


class RHAbstractList(RHAbstractListBase):
    """Display the list of abstracts"""

    def _process(self):
        if self.list_generator.static_link_used:
            return redirect(self.list_generator.get_list_url())
        list_kwargs = self.list_generator.get_list_kwargs()
        return WPManageAbstracts.render_template('management/abstract_list.html', self._conf, event=self.event_new,
                                                 **list_kwargs)


class RHAbstractListCustomize(RHAbstractListBase):
    """Filter options and columns to display for the abstract list of an event"""

    def _process_GET(self):
        list_config = self.list_generator._get_config()
        return WPManageAbstracts.render_template('management/abstract_list_filter.html', self._conf,
                                                 event=self.event_new, visible_items=list_config['items'],
                                                 static_items=self.list_generator.static_items,
                                                 filters=list_config['filters'])

    def _process_POST(self):
        self.list_generator.store_configuration()
        return jsonify_data(flash=False, **self.list_generator.render_list())


class RHAbstractListStaticURL(RHAbstractListBase):
    """Generate a static URL for the configuration of the abstract list"""

    def _process(self):
        return jsonify(url=self.list_generator.generate_static_url())