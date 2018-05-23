from django.core.exceptions import ImproperlyConfigured

import pytest

from rest_polymorphic.serializers import PolymorphicSerializer
from rest_polymorphic.renderers import PolymorphicRenderer

from tests.models import BlogBase, BlogOne, BlogTwo
from tests.serializers import BlogPolymorphicSerializer, BlogOneSerializer

pytestmark = pytest.mark.django_db


class TestPolymorphicSerializer:

    def test_model_serializer_mapping_is_none(self):
        class EmptyPolymorphicSerializer(PolymorphicSerializer):
            pass

        with pytest.raises(ImproperlyConfigured) as excinfo:
            EmptyPolymorphicSerializer()

        assert str(excinfo.value) == (
            '`EmptyPolymorphicSerializer` is missing a '
            '`EmptyPolymorphicSerializer.model_serializer_mapping` attribute'
        )

    def test_resource_type_field_name_is_not_string(self, mocker):
        class NotStringPolymorphicSerializer(PolymorphicSerializer):
            model_serializer_mapping = mocker.MagicMock
            resource_type_field_name = 1

        with pytest.raises(ImproperlyConfigured) as excinfo:
            NotStringPolymorphicSerializer()

        assert str(excinfo.value) == (
            '`NotStringPolymorphicSerializer.resource_type_field_name` must '
            'be a string'
        )

    def test_each_serializer_has_context(self, mocker):
        context = mocker.MagicMock()
        serializer = BlogPolymorphicSerializer(context=context)
        for inner_serializer in serializer.model_serializer_mapping.values():
            assert inner_serializer.context == context

    def test_serialize(self):
        instance = BlogBase.objects.create(name='blog', slug='blog')
        serializer = BlogPolymorphicSerializer(instance)
        assert serializer.data == {
            'name': 'blog',
            'slug': 'blog',
            'resourcetype': 'BlogBase',
        }

    def test_deserialize(self):
        data = {
            'name': 'blog',
            'slug': 'blog',
            'resourcetype': 'BlogBase',
        }
        serializers = BlogPolymorphicSerializer(data=data)
        assert serializers.is_valid()
        assert serializers.data == data

    def test_deserialize_with_invalid_resourcetype(self):
        data = {
            'name': 'blog',
            'resourcetype': 'Invalid',
        }
        serializers = BlogPolymorphicSerializer(data=data)
        assert not serializers.is_valid()

    def test_create(self):
        data = [
            {
                'name': 'a',
                'slug': 'a',
                'resourcetype': 'BlogBase'
            },
            {
                'name': 'b',
                'slug': 'b',
                'info': 'info',
                'resourcetype': 'BlogOne'
            },
            {
                'name': 'c',
                'slug': 'c',
                'resourcetype': 'BlogTwo'
            },
        ]
        serializer = BlogPolymorphicSerializer(data=data, many=True)
        assert serializer.is_valid()

        instances = serializer.save()
        assert len(instances) == 3
        assert [item.name for item in instances] == ['a', 'b', 'c']

        assert BlogBase.objects.count() == 3
        assert BlogBase.objects.instance_of(BlogOne).count() == 1
        assert BlogBase.objects.instance_of(BlogTwo).count() == 1

        assert serializer.data == data

    def test_update(self):
        instance = BlogBase.objects.create(name='blog', slug='blog')
        data = {
            'name': 'new-blog',
            'slug': 'blog',
            'resourcetype': 'BlogBase'
        }

        serializer = BlogPolymorphicSerializer(instance, data=data)
        assert serializer.is_valid()

        serializer.save()
        assert instance.name == 'new-blog'
        assert instance.slug == 'blog'

    def test_partial_update(self):
        instance = BlogBase.objects.create(name='blog', slug='blog')
        data = {
            'name': 'new-blog',
            'resourcetype': 'BlogBase'
        }

        serializer = BlogPolymorphicSerializer(
            instance, data=data, partial=True
        )
        assert serializer.is_valid()

        serializer.save()
        assert instance.name == 'new-blog'
        assert instance.slug == 'blog'

    def test_object_validators_are_applied(self):
        data = {
            'name': 'test-blog',
            'slug': 'test-blog-slug',
            'info': 'test-blog-info',
            'about': 'test-blog-about',
            'resourcetype': 'BlogThree'
        }
        serializer = BlogPolymorphicSerializer(data=data)
        assert serializer.is_valid()
        serializer.save()

        data['slug'] = 'test-blog-slug-new'
        duplicate = BlogPolymorphicSerializer(data=data)
        
        assert not duplicate.is_valid()
        assert 'non_field_errors' in duplicate.errors
        err = duplicate.errors['non_field_errors']

        assert err == ['The fields info, about must make a unique set.']


class TestPolymorphicRenderer:

    def test_polymorphic_renderer_non_polymorphic_serializer(self):
        data = {
            'name': 'test-blog',
            'slug': 'test-blog-slug',
            'info': 'test-blog-info'
        }
        blog = BlogOne.objects.create(**data)

        renderer = PolymorphicRenderer()
        setattr(renderer, 'accepted_media_type', 'text/html')

        non_poly_serializer = BlogOneSerializer(blog)
        non_poly_form = renderer.render_form_for_serializer(non_poly_serializer)

        poly_instance_serializer = BlogPolymorphicSerializer(blog)
        poly_instance_form = renderer.render_form_for_serializer(poly_instance_serializer)

        assert not isinstance(non_poly_form, tuple)
        assert not isinstance(poly_instance_form, tuple)
        for k, v in data.items():
            assert 'name="{}"'.format(k) in poly_instance_form
            assert 'name="{}"'.format(k) in non_poly_form
            assert 'value="{}"'.format(v) in poly_instance_form
            assert 'value="{}"'.format(v) in non_poly_form

    def test_polymorphic_renderer(self):
        renderer = PolymorphicRenderer()
        setattr(renderer, 'accepted_media_type', 'text/html')
        poly_serializer = BlogPolymorphicSerializer()
        form = renderer.render_form_for_serializer(poly_serializer)
        assert isinstance(form, tuple)
        models_found = {f[0]: f[1] for f in form}
        assert 'BlogBase' in models_found
        assert 'BlogOne' in models_found
        assert 'BlogTwo' in models_found
        assert 'name="info"' not in models_found['BlogBase']
        assert 'name="info"' in models_found['BlogOne']
