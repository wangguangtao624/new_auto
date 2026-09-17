# Rust Development Standards

> For Rust projects using Cargo.

- **Scope**: All Rust files in the project (see [core-rules §3.3](../core-rules.md)).

---

## 1. Project Structure

```
project/
├── src/
│   ├── main.rs
│   ├── lib.rs
│   └── modules/
├── tests/
├── .agent/
├── Cargo.toml
└── README.md
```

---

## 2. Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Crate | snake_case | `my_crate` |
| Module | snake_case | `user_manager` |
| Type/Struct | PascalCase | `UserManager` |
| Enum | PascalCase | `Status` |
| Function | snake_case | `get_user_by_id` |
| Constant | UPPER_SNAKE | `MAX_RETRIES` |

---

## 3. Error Handling

```rust
// Define custom errors
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

// Use Result
pub fn get_user(id: u64) -> Result<User, AppError> {
    users.get(&id)
        .cloned()
        .ok_or_else(|| AppError::NotFound(format!("User {}", id)))
}
```

---

## 4. Option Handling

```rust
// Good: Use combinators
let name = user.name.unwrap_or_default();
let upper = user.name.map(|n| n.to_uppercase());

// Good: Early return with ?
fn process(data: Option<Data>) -> Option<Result> {
    let data = data?;
    Some(transform(data))
}
```

---

## 5. Async

```rust
use tokio;

#[tokio::main]
async fn main() {
    let result = fetch_data().await;
}

async fn fetch_data() -> Result<Data, Error> {
    let client = reqwest::Client::new();
    let response = client.get(url).send().await?;
    Ok(response.json().await?)
}
```

---

## 6. Testing

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_user_creation() {
        let user = User::new("test");
        assert_eq!(user.name, "test");
    }

    #[tokio::test]
    async fn test_async_fetch() {
        let result = fetch_data().await;
        assert!(result.is_ok());
    }
}
```

---

## 7. Documentation

```rust
/// Calculates the total price including tax.
///
/// # Arguments
///
/// * `items` - List of items
/// * `tax_rate` - Tax rate (e.g., 0.1 for 10%)
///
/// # Returns
///
/// Total price with tax
///
/// # Examples
///
/// ```
/// let total = calculate_total(&items, 0.1);
/// assert_eq!(total, 110.0);
/// ```
pub fn calculate_total(items: &[Item], tax_rate: f64) -> f64 {
    // ...
}
```

---

## 8. Commands

```bash
# Build
cargo build --release

# Test
cargo test

# Lint
cargo clippy

# Format
cargo fmt

# Check
cargo check
```

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
