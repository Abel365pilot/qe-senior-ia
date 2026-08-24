Feature: Cliente reutilizable para consultar un carrito

  Scenario:
    Given url baseUrl
    And header X-QE-Run-Id = runId
    And path 'carts', cartId
    When method get
