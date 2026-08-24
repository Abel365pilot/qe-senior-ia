Feature: Cliente reutilizable para eliminar un carrito

  Scenario:
    Given url baseUrl
    And path 'carts', cartId
    When method delete
