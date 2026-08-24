package toolshop.support;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Map;

public final class CartTotals {

    private static final BigDecimal ONE_HUNDRED = new BigDecimal("100");

    private CartTotals() {
    }

    public static double total(List<Map<String, Object>> items, Number cartDiscountPercentage) {
        BigDecimal subtotal = items.stream()
                .map(CartTotals::lineTotal)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal cartDiscount = percentage(cartDiscountPercentage);
        return subtotal.multiply(BigDecimal.ONE.subtract(cartDiscount))
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();
    }

    private static BigDecimal lineTotal(Map<String, Object> item) {
        Number quantity = requiredNumber(item, "quantity");
        BigDecimal unitPrice;

        if (item.get("discounted_price") instanceof Number discountedPrice) {
            unitPrice = decimal(discountedPrice);
        } else {
            @SuppressWarnings("unchecked")
            Map<String, Object> product = (Map<String, Object>) item.get("product");
            if (product == null) {
                throw new IllegalArgumentException("Cada item debe incluir product");
            }
            unitPrice = decimal(requiredNumber(product, "price"))
                    .multiply(BigDecimal.ONE.subtract(percentage((Number) item.get("discount_percentage"))));
        }

        return unitPrice.multiply(decimal(quantity));
    }

    private static Number requiredNumber(Map<String, Object> value, String key) {
        Object candidate = value.get(key);
        if (!(candidate instanceof Number number)) {
            throw new IllegalArgumentException(key + " debe ser numerico");
        }
        return number;
    }

    private static BigDecimal percentage(Number value) {
        return value == null
                ? BigDecimal.ZERO
                : decimal(value).divide(ONE_HUNDRED, 8, RoundingMode.HALF_UP);
    }

    private static BigDecimal decimal(Number value) {
        return new BigDecimal(value.toString());
    }
}
