package toolshop.support;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

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

    @Test
    void usesPublishedLineDiscountWhenDiscountedPriceIsAbsent() {
        var items = List.<Map<String, Object>>of(Map.of(
                "quantity", 3,
                "discount_percentage", 10,
                "product", Map.of("price", 20.00)
        ));

        assertEquals(51.30, CartTotals.total(items, 5));
    }

    @Test
    void rejectsInvalidQuantityAndDiscountBoundaries() {
        var fractionalQuantity = List.<Map<String, Object>>of(Map.of(
                "quantity", 1.5,
                "product", Map.of("price", 10.00)
        ));
        var validItem = List.<Map<String, Object>>of(Map.of(
                "quantity", 1,
                "product", Map.of("price", 10.00)
        ));

        assertThrows(IllegalArgumentException.class, () -> CartTotals.total(fractionalQuantity, 0));
        assertThrows(IllegalArgumentException.class, () -> CartTotals.total(validItem, 101));
        assertThrows(IllegalArgumentException.class, () -> CartTotals.total(validItem, -1));
    }

    @Test
    void rejectsIncompleteOrNonFiniteMonetaryData() {
        var missingProduct = List.<Map<String, Object>>of(Map.of("quantity", 1));
        var nonFinitePrice = List.<Map<String, Object>>of(Map.of(
                "quantity", 1,
                "product", Map.of("price", Double.NaN)
        ));

        assertThrows(IllegalArgumentException.class, () -> CartTotals.total(missingProduct, 0));
        assertThrows(IllegalArgumentException.class, () -> CartTotals.total(nonFinitePrice, 0));
    }
}
