Feature: Cliente reutilizable para agregar un producto al carrito

  Scenario:
    Given url baseUrl
    And path 'carts', cartId
    And request { product_id: '#(productId)', quantity: '#(quantity)' }
    When method post
