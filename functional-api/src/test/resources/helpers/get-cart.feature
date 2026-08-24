Feature: Cliente reutilizable para consultar un carrito

  Scenario:
    Given url baseUrl
    And path 'carts', cartId
    When method get
