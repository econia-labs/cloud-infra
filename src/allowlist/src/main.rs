// cspell:word sadd
// cspell:word sismember
// cspell:word thiserror

use std::env::VarError;

use axum::{
    async_trait,
    extract::{rejection::PathRejection, FromRef, FromRequestParts, Path},
    http::{request::Parts, StatusCode},
    routing::get,
    Json, Router,
};
use bb8::{Pool, PooledConnection, RunError};
use bb8_redis::RedisConnectionManager;
use futures::future::FutureExt;
use move_core_types::account_address::{AccountAddress, AccountAddressParseError};
use redis::{AsyncCommands, RedisError};
use serde::Serialize;
use tokio::signal;
use tracing::info;

/// The request path specifier for the request address.
const REQUEST_PATH: &str = "/:request_address";

/// The name of the Redis set that contains the allowlist.
const SET_NAME: &str = "allowlist";

/// A tuple containing a status code and a JSON-serialized request summary.
type CodedSummary = (StatusCode, Json<RequestSummary>);

/// The connection pool for the Redis database.
type ConnectionPool = Pool<RedisConnectionManager>;

/// The result of a request, which is either a successful response or an error response.
type RequestResult = Result<CodedSummary, CodedSummary>;

/// Connection to the Redis database with a default request summary and parsed address.
struct PreparedConnection(
    PooledConnection<'static, RedisConnectionManager>,
    RequestSummary,
    String,
);

/// Environment variables used by the server.
#[derive(strum_macros::Display)]
enum EnvironmentVariable {
    #[strum(to_string = "REDIS_URL")]
    RedisURL,
    #[strum(to_string = "SERVER_URL")]
    ServerURL,
}

/// Errors that can occur when reading environment variables.
#[derive(thiserror::Error, Debug)]
enum EnvironmentVariableError {
    #[error("Could not parse Redis URL environment variable: {0}")]
    RedisURL(VarError),
    #[error("Could not server URL environment variable: {0}")]
    ServerURL(VarError),
}

/// Literals for Redis ping pong check.
#[derive(strum_macros::Display)]
enum PingPong {
    #[strum(to_string = "PING")]
    Ping,
    #[strum(to_string = "PONG")]
    Pong,
}

/// Errors that can occur when initializing the server.
#[derive(thiserror::Error, Debug)]
enum InitError {
    #[error("Could not bind listener: {0}")]
    BindListener(std::io::Error),
    #[error("Failed to install Ctrl+C handler: {0}")]
    CtrlCHandler(std::io::Error),
    #[error("Could not get a connection from the connection manager: {0}")]
    Connection(RunError<RedisError>),
    #[error("Could not start a Redis connection manager: {0}")]
    ConnectionManager(RedisError),
    #[error("Redis connection init ping unsuccessful: {0}")]
    Ping(RunError<RedisError>),
    #[error("Redis connection init ping did not pong correctly: {0}")]
    Pong(String),
    #[error("Redis connection init pool error: {0}")]
    Pool(RedisError),
    #[error("Could not serve listener: {0}")]
    ServeListener(std::io::Error),
    #[error("Failed to install SIGTERM handler: {0}")]
    SIGTERMHandler(std::io::Error),
}

#[derive(strum_macros::Display)]
enum InfoMessage {
    #[strum(to_string = "Added address {0} to allowlist")]
    AddedToAllowlist(String),
    #[strum(to_string = "Starting Redis connection at {0}")]
    ConnectingToRedis(String),
    #[strum(to_string = "Redis ping pong check completed successfully")]
    RedisPingPongCheck,
    #[strum(to_string = "Request received for unparsed address {0}")]
    RequestAddress(String),
    #[strum(to_string = "Server listening on {0}")]
    ServerListening(String),
    #[strum(to_string = "Starting server at {0}")]
    StartingServer(String),
}

/// Errors that can occur when processing a request.
#[derive(thiserror::Error, Debug)]
enum RequestError {
    #[error("Add member error: {0}")]
    AddMember(RedisError),
    #[error("Could not parse address: {0}")]
    CouldNotParseAddress(AccountAddressParseError),
    #[error("Could not parse address request path: {0}")]
    CouldNotParseRequestPath(PathRejection),
    #[error("Is member lookup error: {0}")]
    IsMemberLookup(RedisError),
    #[error("Redis connection error: {0}")]
    RedisConnection(RunError<RedisError>),
}

/// Summary of a server request, returned to user upon query.
#[derive(Clone, Serialize)]
struct RequestSummary {
    /// The address provided by the user during the request, for example `0001234`.
    request_address: String,
    /// AIP-40 hex literal used for database operations, for example `0x1234`.
    parsed_address: Option<String>,
    /// Whether the address is allowed.
    is_allowed: Option<bool>,
    /// Additional information about the request.
    message: String,
}

/// Result of a Redis set operation.
enum SetOperationResult {
    AddedToSet,
    IsMember,
}

/// Happy path summary messages.
#[derive(strum_macros::Display)]
enum SummaryMessage {
    #[strum(to_string = "Added to allowlist")]
    AddedToAllowlist,
    #[strum(to_string = "Already allowed")]
    AlreadyAllowed,
    #[strum(to_string = "Found in allowlist")]
    FoundInAllowlist,
    #[strum(to_string = "Not found in allowlist")]
    NotFoundInAllowlist,
}

/// Integer representation of a Redis set operation result.
impl From<SetOperationResult> for i32 {
    fn from(result: SetOperationResult) -> Self {
        match result {
            SetOperationResult::AddedToSet => 1,
            SetOperationResult::IsMember => 1,
        }
    }
}

/// Load environment variables and start the server.
#[tokio::main]
async fn main() -> Result<(), String> {
    // Get environment variables, initialize logging.
    let redis_url = std::env::var(EnvironmentVariable::RedisURL.to_string())
        .map_err(|error| EnvironmentVariableError::RedisURL(error).to_string())?;
    let listener_url = std::env::var(EnvironmentVariable::ServerURL.to_string())
        .map_err(|error| EnvironmentVariableError::ServerURL(error).to_string())?;
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    // Start Redis connection.
    info!("{}", InfoMessage::ConnectingToRedis(redis_url.clone()));
    let manager = RedisConnectionManager::new(redis_url)
        .map_err(|error| InitError::ConnectionManager(error).to_string())?;
    let pool = bb8::Pool::builder()
        .build(manager)
        .await
        .map_err(|error| InitError::Pool(error).to_string())?;

    // Verify Redis ping pong check.
    {
        let mut connection = pool
            .get()
            .await
            .map_err(|error| InitError::Connection(error).to_string())?;
        let pong = redis::cmd(&PingPong::Ping.to_string())
            .query_async(&mut *connection)
            .await
            .map_err(|error| InitError::Ping(RunError::User(error)).to_string())?;
        if pong != PingPong::Pong.to_string() {
            return Err(InitError::Pong(pong).to_string());
        };
    }
    info!("{}", InfoMessage::RedisPingPongCheck);

    // Start the server.
    info!("{}", InfoMessage::StartingServer(listener_url.clone()));
    let app = Router::new()
        .route(REQUEST_PATH, get(is_allowed).post(add_to_allowlist))
        .with_state(pool);
    let listener = tokio::net::TcpListener::bind(listener_url.clone())
        .await
        .map_err(|error| InitError::BindListener(error).to_string())?;
    info!("{}", InfoMessage::ServerListening(listener_url));
    axum::serve(listener, app)
        .with_graceful_shutdown(
            // Await shutdown signal, returning early if it errors out, then map the output of a
            // successful future to be of unit type for use as a graceful shutdown signal.
            async {
                shutdown_signal().await?;
                Ok(())
            }
            .map(|_: Result<(), String>| ()),
        )
        .await
        .map_err(|error| InitError::ServeListener(error).to_string())?;
    Ok(())
}

/// Check if an address is allowed.
async fn is_allowed(
    PreparedConnection(mut connection, mut request_summary, parsed_address): PreparedConnection,
) -> RequestResult {
    if connection
        .sismember::<&str, &str, i32>(SET_NAME, &parsed_address)
        .await
        .map_err(|error| {
            map_error(
                StatusCode::INTERNAL_SERVER_ERROR,
                request_summary.clone(),
                RequestError::IsMemberLookup(error),
            )
        })?
        == i32::from(SetOperationResult::IsMember)
    {
        request_summary.is_allowed = Some(true);
        request_summary.message = SummaryMessage::FoundInAllowlist.to_string();
    } else {
        request_summary.is_allowed = Some(false);
        request_summary.message = SummaryMessage::NotFoundInAllowlist.to_string();
    }
    Ok((StatusCode::OK, Json(request_summary)))
}

/// Add an address to the allowlist.
async fn add_to_allowlist(
    PreparedConnection(mut connection, mut request_summary, parsed_address): PreparedConnection,
) -> RequestResult {
    if connection
        .sadd::<&str, &str, i32>(SET_NAME, &parsed_address)
        .await
        .map_err(|error| {
            map_error(
                StatusCode::INTERNAL_SERVER_ERROR,
                request_summary.clone(),
                RequestError::AddMember(error),
            )
        })?
        == i32::from(SetOperationResult::AddedToSet)
    {
        info!("{}", InfoMessage::AddedToAllowlist(parsed_address.clone()));
        request_summary.message = SummaryMessage::AddedToAllowlist.to_string();
    } else {
        request_summary.message = SummaryMessage::AlreadyAllowed.to_string();
    };
    request_summary.is_allowed = Some(true);
    Ok((StatusCode::OK, Json(request_summary)))
}

/// Map an arbitrary error into a status code and a request summary.
fn map_error(
    status_code: StatusCode,
    request_summary: RequestSummary,
    request_error: RequestError,
) -> CodedSummary {
    (
        status_code,
        Json(RequestSummary {
            message: request_error.to_string(),
            ..request_summary
        }),
    )
}

/// Custom extractor to parse an address and a get a connection to the Redis database.
#[async_trait]
impl<S> FromRequestParts<S> for PreparedConnection
where
    ConnectionPool: FromRef<S>,
    S: Send + Sync,
{
    type Rejection = CodedSummary;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        // Construct default request summary.
        let mut request_summary = RequestSummary {
            request_address: "".to_string(),
            parsed_address: None,
            is_allowed: None,
            message: "".to_string(),
        };

        // Parse request address by accessing a nested extractor.
        let Path(request_address): Path<String> = Path::from_request_parts(parts, state)
            .await
            .map_err(|error| {
                map_error(
                    StatusCode::BAD_REQUEST,
                    request_summary.clone(),
                    RequestError::CouldNotParseRequestPath(error),
                )
            })?;
        info!("{}", InfoMessage::RequestAddress(request_address.clone()));
        request_summary.request_address.clone_from(&request_address);

        // Parse account address.
        let account_address =
            AccountAddress::try_from(request_address.clone()).map_err(|error| {
                map_error(
                    StatusCode::BAD_REQUEST,
                    request_summary.clone(),
                    RequestError::CouldNotParseAddress(error),
                )
            })?;
        let parsed_address = account_address.to_hex_literal();
        request_summary.parsed_address = Some(parsed_address.clone());

        // Get a connection to the Redis database.
        let pool = ConnectionPool::from_ref(state);
        let connection = pool.get_owned().await.map_err(|error| {
            map_error(
                StatusCode::INTERNAL_SERVER_ERROR,
                request_summary.clone(),
                RequestError::RedisConnection(error),
            )
        })?;
        Ok(Self(connection, request_summary, parsed_address))
    }
}

async fn shutdown_signal() -> Result<(), String> {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .map_err(|error| InitError::CtrlCHandler(error).to_string())?;
        Ok::<(), String>(())
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .map_err(|error| InitError::SIGTERMHandler(error).to_string())?
            .recv()
            .await;
        Ok::<(), String>(())
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        result = ctrl_c => { result },
        result = terminate => { result },
    }
}
