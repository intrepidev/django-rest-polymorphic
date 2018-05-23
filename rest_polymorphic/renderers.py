from rest_framework.renderers import BrowsableAPIRenderer


class PolymorphicRenderer(BrowsableAPIRenderer):
    template = 'rest_polymorphic/api.html'

    def render_form_for_serializer(self, serializer):
        mapping = getattr(serializer, 'model_serializer_mapping', None)

        if mapping:
            # this is a polymorphic serializer
            if hasattr(serializer, 'initial_data'):
                serializer.is_valid()

            if serializer.data:
                # this is a serializer for a particular instance, so it
                # already has a resourctype. Just return the serializer
                # for that resourcetype
                resource_type = serializer._get_resource_type_from_mapping(serializer.data)
                child_serializer = serializer._get_serializer_from_resource_type(resource_type)
                return super(PolymorphicRenderer, self).render_form_for_serializer(child_serializer)
                
            # this serializer is unbound, so return a tuple of all
            # child serializers to use in creation e.g. (('Item', RenderedItemForm), ...)
            return tuple(
                (
                    model.__name__, 
                    super(PolymorphicRenderer, self).render_form_for_serializer(serializer)
                )
                for model, serializer in mapping.items()
            )

        return super(PolymorphicRenderer, self).render_form_for_serializer(serializer)
            

    
    def get_context(self, *args, **kwargs):
        ctx = super(PolymorphicRenderer, self).get_context(*args, **kwargs)
        ctx['is_polymorphic'] = isinstance(ctx['post_form'], tuple)
        return ctx