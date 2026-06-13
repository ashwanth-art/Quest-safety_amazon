import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

MARKETPLACE_ID = os.getenv("MARKETPLACE_ID", "ATVPDKIKX0DER")

LWA_ENDPOINT = "https://api.amazon.com/auth/o2/token"
SP_API_SANDBOX_BASE_URL = "https://sandbox.sellingpartnerapi-na.amazon.com"


# ---------------------------------------------------------
# 2. GET ACCESS TOKEN
# ---------------------------------------------------------

def get_lwa_access_token():
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(LWA_ENDPOINT, data=payload, headers=headers)

    print("Token API Status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise Exception("Failed to generate access token")

    print("Access token generated successfully.")
    return response.json()["access_token"]


# ---------------------------------------------------------
# 3. CATALOG SEARCH API - WORKING SANDBOX MOCK
# ---------------------------------------------------------

def search_catalog_sandbox(access_token):
    url = f"{SP_API_SANDBOX_BASE_URL}/catalog/2022-04-01/items"

    headers = {
        "x-amz-access-token": access_token,
        "Content-Type": "application/json"
    }

    params = {
        "keywords": "samsung,tv",
        "marketplaceIds": MARKETPLACE_ID,
        "includedData": "classifications,dimensions,identifiers,images,productTypes,relationships,salesRanks,summaries,vendorDetails"
    }

    response = requests.get(url, headers=headers, params=params)

    print("\n================ CATALOG SEARCH API ================")
    print("Status:", response.status_code)

    if response.status_code != 200:
        print(json.dumps(response.json(), indent=2))
        return

    data = response.json()

    for item in data.get("items", []):
        asin = item.get("asin")

        summary = item.get("summaries", [{}])[0]
        product_name = summary.get("itemName")
        brand = summary.get("brand")
        manufacturer = summary.get("manufacturer")
        model_number = summary.get("modelNumber")

        product_type = ""
        if item.get("productTypes"):
            product_type = item["productTypes"][0].get("productType")

        upc = ""
        if item.get("identifiers"):
            for identifier in item["identifiers"][0].get("identifiers", []):
                if identifier.get("identifierType") == "UPC":
                    upc = identifier.get("identifier")

        print("\n========== CATALOG PRODUCT SUMMARY ==========")
        print(f"ASIN: {asin}")
        print(f"Product Name: {product_name}")
        print(f"Brand: {brand}")
        print(f"Manufacturer: {manufacturer}")
        print(f"Model Number: {model_number}")
        print(f"Product Type: {product_type}")
        print(f"UPC: {upc}")


# ---------------------------------------------------------
# 4. PRODUCT PRICING COMPETITIVE SUMMARY - WORKING SANDBOX MOCK
# ---------------------------------------------------------

def get_competitive_summary_sandbox(access_token):
    url = f"{SP_API_SANDBOX_BASE_URL}/batches/products/pricing/2022-05-01/items/competitiveSummary"

    headers = {
        "x-amz-access-token": access_token,
        "Content-Type": "application/json"
    }

    # IMPORTANT:
    # Amazon sandbox expects this exact mock request structure.
    body = {
        "requests": [
            {
                "asin": "B00ZIAODGE",
                "marketplaceId": MARKETPLACE_ID,
                "includedData": [
                    "featuredBuyingOptions",
                    "referencePrices",
                    "lowestPricedOffers",
                    "similarItems"
                ],
                "lowestPricedOffersInputs": [
                    {
                        "itemCondition": "New",
                        "offerType": "Consumer"
                    },
                    {
                        "itemCondition": "Used",
                        "offerType": "Consumer"
                    }
                ],
                "uri": "/products/pricing/2022-05-01/items/competitiveSummary",
                "method": "GET"
            },
            {
                "asin": "11_AABB_123",
                "marketplaceId": MARKETPLACE_ID,
                "includedData": [
                    "featuredBuyingOptions"
                ],
                "uri": "/products/pricing/2022-05-01/items/competitiveSummary",
                "method": "GET"
            }
        ]
    }

    response = requests.post(url, headers=headers, json=body)

    print("\n================ COMPETITIVE SUMMARY API ================")
    print("Status:", response.status_code)

    if response.status_code != 200:
        print(json.dumps(response.json(), indent=2))
        return

    print_competitor_summary(response.json())


# ---------------------------------------------------------
# 5. CLEAN COMPETITOR OUTPUT
# ---------------------------------------------------------

def print_competitor_summary(data):
    print("\n========== CLEAN COMPETITOR SUMMARY ==========")

    for result in data.get("responses", []):
        status_code = result.get("status", {}).get("statusCode")
        body = result.get("body", {})

        asin = body.get("asin")
        marketplace_id = body.get("marketplaceId")

        print(f"\nASIN: {asin}")
        print(f"Marketplace: {marketplace_id}")
        print(f"Status: {status_code}")

        if status_code != 200:
            print("Error:", body.get("errors"))
            continue

        print("\nFeatured Offers:")

        for buying_option in body.get("featuredBuyingOptions", []):
            for offer in buying_option.get("segmentedFeaturedOffers", []):
                seller_id = offer.get("sellerId")
                condition = offer.get("condition")
                fulfillment = offer.get("fulfillmentType")

                listing_price = offer.get("listingPrice", {})
                price = listing_price.get("amount", 0)
                currency = listing_price.get("currencyCode", "USD")

                shipping = 0
                shipping_options = offer.get("shippingOptions", [])
                if shipping_options:
                    shipping = shipping_options[0].get("price", {}).get("amount", 0)

                total = round(price + shipping, 2)

                print(f"- Seller: {seller_id}")
                print(f"  Condition: {condition}")
                print(f"  Fulfillment: {fulfillment}")
                print(f"  Listing Price: {currency} {price}")
                print(f"  Shipping: {currency} {shipping}")
                print(f"  Total Price: {currency} {total}")

        print("\nLowest Priced Offers:")

        for offer_group in body.get("lowestPricedOffers", []):
            condition_group = offer_group.get("lowestPricedOffersInput", {}).get("itemCondition")

            print(f"\nCondition Group: {condition_group}")

            for offer in offer_group.get("offers", []):
                seller_id = offer.get("sellerId")
                condition = offer.get("condition")
                fulfillment = offer.get("fulfillmentType")
                prime = offer.get("primeDetails", {}).get("eligibility")

                listing_price = offer.get("listingPrice", {})
                price = listing_price.get("amount", 0)
                currency = listing_price.get("currencyCode", "USD")

                shipping = 0
                shipping_options = offer.get("shippingOptions", [])
                if shipping_options:
                    shipping = shipping_options[0].get("price", {}).get("amount", 0)

                total = round(price + shipping, 2)

                print(f"- Seller: {seller_id}")
                print(f"  Condition: {condition}")
                print(f"  Fulfillment: {fulfillment}")
                print(f"  Prime: {prime}")
                print(f"  Listing Price: {currency} {price}")
                print(f"  Shipping: {currency} {shipping}")
                print(f"  Total Price: {currency} {total}")

        print("\nReference Prices:")

        for ref in body.get("referencePrices", []):
            name = ref.get("name")
            price_obj = ref.get("price", {})
            amount = price_obj.get("amount")
            currency = price_obj.get("currencyCode", "USD")

            print(f"- {name}: {currency} {amount}")

        print("\nSimilar ASINs:")

        for group in body.get("similarItems", []):
            for item in group.get("items", []):
                print(f"- {item.get('asin')}")


# ---------------------------------------------------------
# 6. RUN
# ---------------------------------------------------------

if __name__ == "__main__":
    try:
        token = get_lwa_access_token()

        search_catalog_sandbox(token)

        get_competitive_summary_sandbox(token)

    except Exception as error:
        print("Error:", error)