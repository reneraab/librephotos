import operator
from functools import reduce

from django.db.models import Q
from django.db.models.expressions import RawSQL
from rest_framework import filters
from rest_framework.compat import distinct

from api.image_similarity import search_similar_embedding
from api.semantic_search.semantic_search import semantic_search_instance


class SemanticSearchFilter(filters.SearchFilter):
    def filter_queryset(self, request, queryset, view):
        search_fields = self.get_search_fields(view, request)
        search_terms = self.get_search_terms(request)

        if not search_fields or not search_terms:
            return queryset

        orm_lookups = [
            self.construct_search(str(search_field)) for search_field in search_fields
        ]

        if request.user.semantic_search_topk > 0:
            query = request.query_params.get("search")
            emb, magnitude = semantic_search_instance.calculate_query_embeddings(query)
            semantic_search_instance.unload()

            image_hashes = search_similar_embedding(
                request.user.id, emb, request.user.semantic_search_topk, threshold=27
            )

        base = queryset
        conditions = []
        for search_term in search_terms:
            queries = [Q(**{orm_lookup: search_term}) for orm_lookup in orm_lookups]

            if request.user.semantic_search_topk > 0:
                queries += [Q(image_hash__in=image_hashes)]

            conditions.append(reduce(operator.or_, queries))
        queryset = queryset.filter(reduce(operator.and_, conditions))

        if self.must_call_distinct(queryset, search_fields):
            # Filtering against a many-to-many field requires us to
            # call queryset.distinct() in order to avoid duplicate items
            # in the resulting queryset.
            # We try to avoid this if possible, for performance reasons.
            queryset = distinct(queryset, base)
        return queryset
