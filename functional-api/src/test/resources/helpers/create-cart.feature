Feature: Cliente reutilizable para crear un carrito

  Scenario:
    Given url baseUrl
    And header X-QE-Run-Id = runId
    And path 'carts'
    And request {}
    When method post
