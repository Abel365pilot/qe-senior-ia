Feature: Cliente reutilizable para eliminar un carrito

  Scenario:
    Given url baseUrl
    And header X-QE-Run-Id = runId
    And path 'carts', cartId
    When method delete
