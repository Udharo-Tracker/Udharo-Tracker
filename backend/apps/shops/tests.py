from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.account.models import User

from .models import Customer, Shop


def make_user_with_shop(email="owner@example.com"):
    user = User.objects.create_user(email=email, password="Str0ngPass!23")
    shop = Shop.objects.create(owner=user, name=f"{email}'s shop")
    return user, shop


class CustomerAPITests(TestCase):
    def setUp(self):
        self.user, self.shop = make_user_with_shop("owner@example.com")
        self.other_user, self.other_shop = make_user_with_shop("intruder@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_customer_scopes_to_own_shop(self):
        response = self.client.post(
            "/api/v1/customers/", {"name": "Ram", "phone": "9800000000"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        customer = Customer.objects.get(pk=response.data["id"])
        self.assertEqual(customer.shop, self.shop)

    def test_list_only_returns_own_shops_customers(self):
        Customer.objects.create(shop=self.shop, name="Ram")
        Customer.objects.create(shop=self.other_shop, name="Shyam")

        response = self.client.get("/api/v1/customers/")

        names = [c["name"] for c in response.data["results"]]
        self.assertEqual(names, ["Ram"])

    def test_cannot_retrieve_another_shops_customer(self):
        other_customer = Customer.objects.create(shop=self.other_shop, name="Shyam")

        response = self.client.get(f"/api/v1/customers/{other_customer.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_another_shops_customer(self):
        other_customer = Customer.objects.create(shop=self.other_shop, name="Shyam")

        response = self.client.delete(f"/api/v1/customers/{other_customer.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Customer.objects.filter(pk=other_customer.id).exists())

    def test_search_filters_by_name_phone_or_email(self):
        Customer.objects.create(shop=self.shop, name="Ram Thapa", phone="9811111111")
        Customer.objects.create(shop=self.shop, name="Shyam Gurung", phone="9822222222")

        response = self.client.get("/api/v1/customers/", {"search": "9811111111"})

        names = [c["name"] for c in response.data["results"]]
        self.assertEqual(names, ["Ram Thapa"])

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(None)

        response = self.client.get("/api/v1/customers/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
