"""
This package contains a series of interface definitions that need to be
implemented by the implemention-dependent backend provider.

"""
import abc
import typing

from .deferred import Deferred


class MutatorDescriptor(metaclass=abc.ABCMeta):
    def raise_immutable_attribute_error(self) -> None:
        ...  # pragma: nocover


class NativeAttributeDescriptor(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeAttributeDescriptor` describes an attribute of a native object,
    which will end up being associated to some resource attribute descriptor(s)
    by :py:class:`Mapper`.

    This class has nothing to do with Python's sense of "descriptors."
    """

    @property
    @abc.abstractmethod
    def type(self) -> typing.Optional[typing.Type]:
        """
        Returns the attribute's type which this descriptor describes.
        In case the type is indeterminable, returns None.
        """
        ...  # pragma: nocover

    @property
    @abc.abstractmethod
    def allow_null(self) -> bool:
        """
        Returns the attribute's nullability which this descriptor describes.
        """
        ...  # pragma: nocover

    @property
    @abc.abstractmethod
    def name(self) -> typing.Optional[str]:
        """
        Returns the attribute's name which this descriptor describes.
        In case the type is indeterminable, returns None.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def fetch_value(self, target: typing.Any) -> typing.Any:
        """
        Fetches a value from the target native object that corresponds to the attribute
        described by it.

        :param Any target: A native object from which the attribute's value is fetched.
        :return: The fetched attribute value.
        """
        ...  # pragma: nocover


class NativeRelationshipDescriptor(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeRelationshipDescriptor` describes a relationship of two native objects,
    which will end up being associated to a resource relationship descriptor
    by :py:class:`Mapper`.  This is a super-interfaces of the following interfaces:

    * :py:class:`NativeToOneRelationshipDescriptor`
    * :py:class:`NativeToManyRelationshipDescriptor`

    This class has nothing to do with Python's sense of "descriptors."
    """

    @property
    @abc.abstractmethod
    def name(self) -> typing.Optional[str]:
        """
        Returns the attribute's name which this descriptor describes.
        In case the type is indeterminable, returns None.
        """
        ...  # pragma: nocover

    @property
    @abc.abstractmethod
    def destination(self) -> "NativeDescriptor":
        """
        Returns the :py:class:`NativeDescriptor` object that describes the other side of
        the relationship.

        :return: The :py:class:`NativeDescriptor` object for the other side of the relationship.
        """
        ...  # pragma: nocover


class NativeToOneRelationshipDescriptor(NativeRelationshipDescriptor):
    """
    A :py:class:`NativeRelationshipDescriptor` describes a one-to-one relationship
    between two native objects.
    """

    @abc.abstractmethod
    def fetch_related(self, target: typing.Any) -> typing.Any:
        """
        Fetches the native object on the other side of the relationship from the target
        native object.

        :param Any target: A native object from which the related object is fetched.
        :return: The fetched object.
        """
        ...  # pragma: nocover


class NativeToManyRelationshipDescriptor(NativeRelationshipDescriptor):
    """
    A :py:class:`NativeRelationshipDescriptor` describes a one-to-many relationship
    between two native objects.
    """

    @abc.abstractmethod
    def fetch_related(self, target: typing.Any) -> typing.Iterable[typing.Any]:
        """
        Returns an iterable that fetches the native objects on the other side
        of the relationship from the target native object.

        :param Any target: A native object from which the related object is fetched.
        :return: The fetched object.
        """
        ...  # pragma: nocover


class MutationContext(metaclass=abc.ABCMeta):
    """
    A :py:class:`MutationContext` denotes a context passed over the call chains between
    the mapper and native object builders accompanied by a method that depends
    on the site state (database connections etc.)
    """


class NativeToOneRelationshipBuilder(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeToOneRelationshipBuilder` constitutes the series of the "builder"
    objects. It is responsible for building a one-to-one relationship
    between two native objects.
    """

    @abc.abstractmethod
    def nullify(self):
        """
        Sets the builder to not having any counterpart.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def set(self, id: typing.Any):
        """
        Sets the builder so that it will yield a counterpart native object.

        :param Any id: A native identifier.
        """
        ...  # pragma: nocover


class NativeToOneRelationshipManipulator(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeToOneRelationshipManipulator` constitutes the series of the "builder"
    objects. It is responsible for modifying a one-to-one relationship
    between two native objects.
    """

    @abc.abstractmethod
    def nullify(self) -> Deferred[bool]:
        """
        Sets the updater to not having any counterpart.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def unset(self, id: typing.Any) -> Deferred[bool]:
        """
        Sets the builder to not having the counterpart native object.

        :param Any id: A native identifier.
        :return: a :py:class:`Deferred` object that will get its value set to a boolean value
                 that indicates if the manipulation is successfully done.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def set(self, id: typing.Any) -> Deferred[bool]:
        """
        Sets the builder so that it will yield a counterpart native object.

        :param Any id: A native identifier.
        :return: a :py:class:`Deferred` object that will get its value set to a boolean value
                 that indicates if the manipulation is successfully done.
        """
        ...  # pragma: nocover


class NativeToManyRelationshipBuilder(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeToManyRelationshipBuilder` constitutes the series of the "builder"
    objects. It is responsible for modifying a one-to-many relationship
    from a single native object to multiple native objects.
    """

    @abc.abstractmethod
    def next(self, id: typing.Any):
        """
        Set the builder so as to have the specified native identifier
        """
        ...  # pragma: nocover


class NativeToManyRelationshipManipulator(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeToManyRelationshipManipulator` represents a batch of
    operations on a one-to-many relationship from a single native object
    to multiple native objects.
    """

    @abc.abstractmethod
    def add(self, id: typing.Any) -> Deferred[bool]:
        """
        Add a new relationship.

        :param Any id: A native identifier.
        :return: a :py:class:`Deferred` object that will get its value set to a boolean value
                 that indicates if the manipulation is successfully done.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def remove(self, id: typing.Any) -> Deferred[bool]:
        """
        Remove an existing relationship.

        :param Any id: A native identifier.
        :return: a :py:class:`Deferred` object that will get its value set to a boolean value
                 that indicates if the manipulation is successfully done.
        """
        ...  # pragma: nocover


class NativeBuilder(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeBuilder` constitutes the series of the "builder" objects.
    It is responsible for building a single native object.
    """

    @abc.abstractmethod
    def __setitem__(self, descr: NativeAttributeDescriptor, v: typing.Any) -> None:
        """
        Sets the attribute described by the specified :py:class:`NativeAttributeDescriptor` to the given value.

        :param NativeAttributeDescriptor descr: The attribute descriptor that represents the attribute.
        :param Any v: The value to set.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def mark_immutable(
        self, descr: NativeAttributeDescriptor, mutator_descr: MutatorDescriptor
    ) -> None:
        """
        Marks the specified attribute as immutable. If the corresponding attribute is to be changed,
        the builder will end up raising :py:class:`ImmutableAttributeError`.

        :param NativeAttributeDescriptor descr: The attribute descriptor that represents the attribute to mark immutable.
        :param MutatorDescriptor mutator_descr: The mutator descriptor that describes a set of resource attribute descriptors.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def to_one_relationship(
        self, descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipBuilder:
        """
        Returns a :py:class:`NativeToOneRelationshipBuilder` to build a one-to-one relationship.

        :param NativeToOneRelationshipDescriptor descr: The relationship descriptor that represents the relationship.
        :return: The relationship builder.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def to_many_relationship(
        self, descr: NativeToManyRelationshipDescriptor
    ) -> NativeToManyRelationshipBuilder:
        """
        Returns a :py:class:`NativeToManyRelationshipBuilder` to build a one-to-many relationship.

        :param NativeToManyRelationshipDescriptor descr: The relationship descriptor that represents the relationship.
        :return: The relationship builder.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def __call__(self, ctx: MutationContext) -> typing.Any:
        """
        Returns a native object built.

        :param MutationContext ctx: A :py:class:`MutationContext` for use in the building process.
        :return: The native object built.
        """
        ...  # pragma: nocover


class NativeUpdater(NativeBuilder):
    @abc.abstractmethod
    def to_one_relationship_manipulator(
        self, descr: NativeToOneRelationshipDescriptor
    ) -> NativeToOneRelationshipManipulator:
        """
        Returns a :py:class:`NativeToOneRelationshipManipulator` to manipulate a one-to-one relationship.

        :param NativeToOneRelationshipDescriptor descr: The relationship descriptor that represents the relationship.
        :return: The relationship manipulator.
        """
        ...  # pragma: nocover

    @abc.abstractmethod
    def to_many_relationship_manipulator(
        self, descr: NativeToManyRelationshipDescriptor
    ) -> NativeToManyRelationshipManipulator:
        """
        Returns a :py:class:`NativeToManyRelationshipManipulator` to manipulator a one-to-many relationship.

        :param NativeToManyRelationshipDescriptor descr: The relationship descriptor that represents the relationship.
        :return: The relationship manipulator.
        """
        ...  # pragma: nocover


class NativeDescriptor(metaclass=abc.ABCMeta):
    """
    A :py:class:`NativeDescriptor` denotes the properties of a native object.
    """

    @property
    @abc.abstractmethod
    def class_(self) -> type:
        """
        Returns the class of the native object that the descriptor denotes.

        :return: A type object that represents the class.
        """

    @abc.abstractmethod
    def new_builder(self) -> NativeBuilder:
        """
        Returns a new :py:class:`NativeBuilder` object for building a native objects.

        :return: A new :py:class:`NativeBuilder` instance.
        """

    @abc.abstractmethod
    def new_updater(self, target: typing.Any) -> NativeUpdater:
        """
        Returns a new :py:class:`NativeUpdater` object for updating a native objects.

        :return: A new :py:class:`NativeUpdater` instance.
        """

    @property
    @abc.abstractmethod
    def attributes(self) -> typing.Sequence[NativeAttributeDescriptor]:
        """
        Returns descriptors for the attributes the native object possesses.

        :return: the sequence of :py:class:`NativeAttributeDescriptor`.
        """

    @abc.abstractmethod
    def get_attribute_by_name(self, name: str) -> NativeAttributeDescriptor:
        """
        Returns an attribute descriptor whose name is ``name``.

        :return: A :py:class:`NativeAttributeDescriptor` instance.
        """

    @property
    @abc.abstractmethod
    def relationships(self) -> typing.Sequence[NativeRelationshipDescriptor]:
        """
        Returns descriptors for the relationships the native object has.

        :return: the sequence of :py:class:`NativeRelationshipDescriptor`.
        """

    @abc.abstractmethod
    def get_relationship_by_name(self, name: str) -> NativeRelationshipDescriptor:
        """
        Returns a relationship descriptor whose name is ``name``.

        :return: A :py:class:`NativeRelationshipDescriptor` instance.
        """

    @abc.abstractmethod
    def get_identity(self, target: typing.Any) -> typing.Any:
        """
        Retrieves the identity for the target native object.

        :return: An implementation-dependent identifier for the native object.
        """
