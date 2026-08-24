package toolshop.support;

import com.intuit.karate.JsonUtils;
import com.intuit.karate.Match;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ContractSchemaTest {

    @Test
    void acceptsRepresentativeResponsesAndOptionalDiscounts() throws IOException {
        Map<String, Object> product = Map.of(
                "id", "product-1",
                "name", "Combination Pliers",
                "description", "A tool",
                "price", 12.50,
                "is_location_offer", false,
                "is_rental", false,
                "in_stock", 10,
                "co2_rating", "A",
                "is_eco_friendly", true
        );
        Map<String, Object> cartItem = Map.of(
                "id", "line-1",
                "cart_id", "cart-1",
                "product_id", "product-1",
                "quantity", 2,
                "discount_percentage", 10,
                "discounted_price", 11.25,
                "product", product
        );

        assertMatches(product, "schemas/product.json");
        assertMatches(cartItem, "schemas/cart-item.json");
        assertMatches(Map.of("id", "cart-1", "cart_items", List.of(cartItem)), "schemas/cart.json");
        assertMatches(Map.of(
                "current_page", 1,
                "data", List.of(product),
                "last_page", 1,
                "per_page", 9,
                "total", 1
        ), "schemas/paginated-products.json");
        assertMatches(Map.of(
                "access_token", "a-token-longer-than-twenty-characters",
                "token_type", "Bearer",
                "expires_in", 3600
        ), "schemas/login-success.json");
        assertMatches(Map.of("error", "Unauthorized"), "schemas/login-error.json");
    }

    @Test
    void rejectsSemanticallyInvalidContractValues() throws IOException {
        Object cartItemSchema = schema("schemas/cart-item.json");
        Map<String, Object> invalidQuantity = Map.of(
                "id", "line-1",
                "cart_id", "cart-1",
                "product_id", "product-1",
                "quantity", 1.5,
                "product", Map.of()
        );

        assertThrows(RuntimeException.class, () -> Match.that(invalidQuantity).contains(cartItemSchema));
    }

    private static void assertMatches(Object actual, String schemaResource) throws IOException {
        Match.Result result = Match.that(actual).contains(schema(schemaResource));
        assertTrue(result.pass, result.message);
    }

    private static Object schema(String resource) throws IOException {
        try (InputStream input = ContractSchemaTest.class.getClassLoader().getResourceAsStream(resource)) {
            assertNotNull(input, resource);
            return JsonUtils.fromJsonStrict(new String(input.readAllBytes(), StandardCharsets.UTF_8));
        }
    }
}
