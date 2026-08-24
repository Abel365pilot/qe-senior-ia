package toolshop.support;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CartTotalsTest {

    @Test
    void calculatesQuantityAndRoundsMoney() {
        var items = List.<Map<String, Object>>of(Map.of(
                "quantity", 2,
                "discount_percentage", 0,
                "product", Map.of("price", 12.345)
        ));

        assertEquals(24.69, CartTotals.total(items, 0));
    }

    @Test
    void appliesItemAndCartDiscounts() {
        var items = List.<Map<String, Object>>of(Map.of(
                "quantity", 2,
                "discounted_price", 9.00,
                "product", Map.of("price", 10.00)
        ));

        assertEquals(15.30, CartTotals.total(items, 15));
    }
}
