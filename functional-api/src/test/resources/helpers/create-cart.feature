Feature: Cliente reutilizable para crear un carrito

  Scenario:
    Given url baseUrl
    And path 'carts'
    And request {}
    When method post
