# app/modules/clothing/prompts.py

CLOTHING_INTENT_PROMPT = """
Analyze the user's WhatsApp message for a clothing store.
Your goal is to extract the user's intent and any specific filters.

Categorize into one of these intents:
- GREETING: User says hello or hi.
- SHOW_PRODUCTS: User wants to see items or browse a category.
- FILTER_PRICE: User mentions a budget or price (e.g., "under 500").
- SELECT_PRODUCT: User specifies a particular item (e.g., "I'll take the black one").
- SHOW_MORE: User wants to see more options.

Return ONLY a valid JSON object with these keys:
{
  "intent": "INTENT_NAME",
  "max_price": integer or null,
  "category": "men" or "women" or null,
  "product_selection": string or null
}
"""