"""
Redis document property classes. Much of the date and time property
code was borrowed or inspired by Benoit Chesneau's CouchDBKit library.
"""

from valley.mixins import CharVariableMixin, IntegerVariableMixin, \
    FloatVariableMixin, SlugVariableMixin, \
    EmailVariableMixin, BooleanMixin, DateMixin, DateTimeMixin
from valley.properties import BaseProperty as VBaseProperty


class BaseProperty(VBaseProperty):

    def __init__(
        self,
        default_value=None,
        required=False,
        global_index=False,

        index_name=None,
        unique=False,
        write_capacity=None,
        read_capacity=None,
        key_type='HASH',
        validators=[],
        verbose_name=None,
        **kwargs
    ):
        super(BaseProperty, self).__init__(default_value=default_value,
                                           required=required,
                                           validators=validators,
                                           verbose_name=verbose_name,
                                           **kwargs)
        self.global_index = global_index

        self.unique = unique
        self.index_name = index_name
        self.key_type = key_type
        self.read_capacity = read_capacity
        self.write_capacity = write_capacity
        if self.global_index is True:
            self.key_type = 'HASH'


class CharProperty(CharVariableMixin,BaseProperty):
    pass


class SlugProperty(SlugVariableMixin,BaseProperty):
    pass


class EmailProperty(EmailVariableMixin,BaseProperty):
    pass


class IntegerProperty(IntegerVariableMixin, BaseProperty):
    pass


class FloatProperty(FloatVariableMixin, BaseProperty):
    pass


class BooleanProperty(BooleanMixin, BaseProperty):
    pass


class DateProperty(DateMixin, BaseProperty):

    def __init__(
            self,
            default_value=None,
            required=True,
            validators=[],
            verbose_name=None,
            auto_now=False,
            auto_now_add=False,
            **kwargs):

        super(
            DateProperty,
            self).__init__(
            default_value=default_value,
            required=required,
            validators=validators,
            verbose_name=verbose_name,
            **kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add


class DateTimeProperty(DateTimeMixin, BaseProperty):

    def __init__(
            self,
            default_value=None,
            required=True,
            validators=[],
            verbose_name=None,
            auto_now=False,
            auto_now_add=False,
            **kwargs):

        super(
            DateTimeProperty,
            self).__init__(
            default_value=default_value,
            required=required,
            validators=validators,
            verbose_name=verbose_name,
            **kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
