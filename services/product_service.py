from models import Product

class ProductService:
    def __init__(self, mongo_client, feature_flags):
        self.mongo_client = mongo_client
        self.products_collection = mongo_client.db.products
        self.feature_flags = feature_flags

    def add_product(self, name, cost, image_url, category, description=''):
        product = Product(name, cost, image_url, category, description)
        self.products_collection.insert_one(product.to_dict())
        return product

    def get_products(self, filters=None):
        query = filters or {}
        products = self.products_collection.find(query)
        return [Product.from_dict(p) for p in products]

    # Search only the exact product name
    def search_products(self, search_term):
        search_term = search_term.strip()

        query = {
            "name": {
                "$regex": f"^{search_term}$",
                "$options": "i"
            }
        }

        products = self.products_collection.find(query)
        return [Product.from_dict(p) for p in products]

    def get_recommendations(self, search_term, user=None):
        matching_products = self.search_products(search_term)

        if not matching_products:
            return []

        categories = [p.category for p in matching_products]

        if self.feature_flags.is_enabled('advanced_recommendations', user):
            return self._get_advanced_recommendations(categories, search_term, user)
        else:
            return self._get_basic_recommendations(categories, search_term)

    # Recommend products from same category except searched product
    def _get_basic_recommendations(self, categories, search_term):

        similar_products = self.products_collection.find({
            "category": {"$in": categories},
            "name": {
                "$ne": search_term
            }
        }).limit(5)

        return [Product.from_dict(p) for p in similar_products]

    def _get_advanced_recommendations(self, categories, search_term, user):

        base_recommendations = self._get_basic_recommendations(categories, search_term)

        additional_query = {
            "$and": [
                {
                    "$or": [
                        {
                            "description": {
                                "$regex": search_term,
                                "$options": "i"
                            }
                        },
                        {
                            "name": {
                                "$regex": f".*{search_term[:3]}.*",
                                "$options": "i"
                            }
                        }
                    ]
                },
                {
                    "name": {
                        "$ne": search_term
                    }
                }
            ]
        }

        additional_products = self.products_collection.find(additional_query).limit(3)

        additional_recommendations = [
            Product.from_dict(p)
            for p in additional_products
        ]

        unique_products = []
        seen = set()

        for product in base_recommendations + additional_recommendations:
            if product.name.lower() not in seen:
                seen.add(product.name.lower())
                unique_products.append(product)

        return unique_products[:8]