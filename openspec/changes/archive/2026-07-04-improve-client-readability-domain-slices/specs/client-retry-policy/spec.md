# Delta Spec: client-retry-policy

## ADDED Requirements

### Requirement: Authentication failures are not retried

The client SHALL treat HTTP `401` and `403` responses as non-retryable
authentication failures: exactly one HTTP request is made and a
`BSBLANAuthError` is raised, without invoking the backoff retry policy.

#### Scenario: 401 response raises auth error after a single request

- **WHEN** the BSB-LAN device responds to a request with HTTP `401` and only
  one mocked response is registered
- **THEN** the client raises `BSBLANAuthError` and no retry request is made

#### Scenario: 403 response raises auth error after a single request

- **WHEN** the BSB-LAN device responds to a request with HTTP `403` and only
  one mocked response is registered
- **THEN** the client raises `BSBLANAuthError` and no retry request is made
