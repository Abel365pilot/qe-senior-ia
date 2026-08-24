package toolshop.support;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public final class CartTotals {

    private static final BigDecimal ONE_HUNDRED = new BigDecimal("100");

    private CartTotals() {
    }

    public static double total(List<Map<String, Object>> items, Number cartDiscountPercentage) {
        Objects.requireNonNull(items, "items no puede ser null");
        BigDecimal subtotal = items.stream()
                .map(CartTotals::lineTotal)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal cartDiscount = percentage(cartDiscountPercentage);
        return subtotal.multiply(BigDecimal.ONE.subtract(cartDiscount))
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();
    }

    private static BigDecimal lineTotal(Map<String, Object> item) {
        Objects.requireNonNull(item, "Un item del carrito no puede ser null");
        Number quantity = requiredNumber(item, "quantity");
        BigDecimal quantityValue = decimal(quantity, "quantity");
        if (quantityValue.signum() <= 0 || quantityValue.stripTrailingZeros().scale() > 0) {
            throw new IllegalArgumentException("quantity debe ser un entero positivo");
        }

        BigDecimal unitPrice;

        if (item.get("discounted_price") instanceof Number discountedPrice) {
            unitPrice = nonNegativeMoney(discountedPrice, "discounted_price");
        } else {
            Object productCandidate = item.get("product");
            if (!(productCandidate instanceof Map<?, ?> product)) {
                throw new IllegalArgumentException("Cada item sin discounted_price debe incluir product");
            }
            unitPrice = nonNegativeMoney(requiredNumber(product, "price"), "product.price")
                    .multiply(BigDecimal.ONE.subtract(percentage(optionalNumber(item, "discount_percentage"), "discount_percentage")));
        }

        return unitPrice.multiply(quantityValue);
    }

    private static Number requiredNumber(Map<?, ?> value, String key) {
        Object candidate = value.get(key);
        if (!(candidate instanceof Number number)) {
            throw new IllegalArgumentException(key + " debe ser numerico");
        }
        return number;
    }

    private static Number optionalNumber(Map<String, Object> value, String key) {
        Object candidate = value.get(key);
        if (candidate == null) {
            return null;
        }
        if (!(candidate instanceof Number number)) {
            throw new IllegalArgumentException(key + " debe ser numerico cuando esta presente");
        }
        return number;
    }

    private static BigDecimal percentage(Number value) {
        return percentage(value, "additional_discount_percentage");
    }

    private static BigDecimal percentage(Number value, String field) {
        if (value == null) {
            return BigDecimal.ZERO;
        }
        BigDecimal percentage = decimal(value, field);
        if (percentage.signum() < 0 || percentage.compareTo(ONE_HUNDRED) > 0) {
            throw new IllegalArgumentException(field + " debe estar entre 0 y 100");
        }
        return percentage.divide(ONE_HUNDRED, 8, RoundingMode.HALF_UP);
    }

    private static BigDecimal nonNegativeMoney(Number value, String field) {
        BigDecimal money = decimal(value, field);
        if (money.signum() < 0) {
            throw new IllegalArgumentException(field + " no puede ser negativo");
        }
        return money;
    }

    private static BigDecimal decimal(Number value, String field) {
        try {
            return new BigDecimal(value.toString());
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(field + " debe ser un numero finito", exception);
        }
    }
}
