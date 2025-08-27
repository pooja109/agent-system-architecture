import structlog
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import uuid

from services.pooled_service_base import PooledServiceBase
from services.databricks_oauth_client import DatabricksOAuthClient
from database.models import EmailRecord

logger = structlog.get_logger(__name__)

class DatabricksClient(PooledServiceBase):
    """Databricks client using connection pooling for optimal performance."""
    
    def __init__(self):
        """Initialize Databricks client with connection pooling."""
        super().__init__()
        
        # Don't get settings in constructor since get_settings is now async
        # Settings will be retrieved when needed
        self._table_name = None
        self._databricks_settings = None
        
    async def _ensure_settings(self):
        """Ensure settings are loaded."""
        if self._table_name is None:
            from config.settings import get_settings
            settings = await get_settings()
            
            self._table_name = f"`{settings.databricks_oauth.catalog}`.`{settings.databricks_oauth.schema_name}`.`email_communication_pipeline{settings.databricks_oauth.table_suffix}`"
            self._databricks_settings = settings.databricks_oauth
        
    # Connection management handled by base class and global pool
    
    async def execute_query(self, query: str, parameters: Optional[List] = None) -> List[Dict[str, Any]]:
        """Execute a query using pooled connection."""
        return await self.execute_with_connection(
            self._execute_query_impl,
            query,
            parameters
        )
    
    async def _execute_query_impl(
        self,
        connection: DatabricksOAuthClient,
        query: str,
        parameters: Optional[List] = None
    ) -> List[Dict[str, Any]]:
        """Implementation of execute query with pooled connection."""
        
        try:
            # Use secure parameter handling through OAuth client
            if parameters:
                # Convert parameters to dict format expected by Databricks SDK
                param_dict = {f"param_{i}": param for i, param in enumerate(parameters)}
                results = await connection.execute_sql_fetchall(query, param_dict)
            else:
                results = await connection.execute_sql_fetchall(query)
            
            logger.debug(f"Query executed successfully, returned {len(results)} rows")
            return results
                
        except Exception as e:
            logger.error("Error executing query", error=str(e), query=query[:100], parameters=parameters)
            raise
    
    async def execute_update(self, query: str, parameters: Optional[List] = None) -> int:
        """Execute an update/insert/delete query using pooled connection."""
        return await self.execute_with_connection(
            self._execute_update_impl,
            query,
            parameters
        )
    
    async def _execute_update_impl(
        self,
        connection: DatabricksOAuthClient,
        query: str,
        parameters: Optional[List] = None
    ) -> int:
        """Implementation of execute update with pooled connection."""
        
        try:
            # Use secure parameter handling through OAuth client
            if parameters:
                # Convert parameters to dict format expected by Databricks SDK
                param_dict = {f"param_{i}": param for i, param in enumerate(parameters)}
                await connection.execute_sql(query, param_dict)
            else:
                await connection.execute_sql(query)
            
            # OAuth client doesn't provide rowcount - assume success if no exception
            logger.debug("Update query executed successfully (assuming 1 row affected)")
            return 1  # Return 1 to indicate successful execution
                
        except Exception as e:
            logger.error("Error executing update query", error=str(e), query=query[:100], parameters=parameters)
            raise
    
    async def create_tables(self) -> bool:
        """Create the email communication pipeline table and related objects."""
        await self._ensure_settings()
        try:
            # Read the schema SQL file
            import os
            schema_file = os.path.join(os.path.dirname(__file__), 'table_schema.sql')
            
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Replace placeholders with actual values
            schema_sql = schema_sql.format(
                catalog=self._databricks_settings.catalog,
                schema=self._databricks_settings.schema_name,
                table_suffix=self._databricks_settings.table_suffix
            )
            
            # Split into individual statements
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            # Execute each statement
            for statement in statements:
                if statement:
                    await self.execute_update(statement)
                    logger.info(f"Executed: {statement[:50]}...")
            
            logger.info("Successfully created tables and views")
            return True
            
        except Exception as e:
            logger.error("Failed to create tables", error=str(e))
            return False
    
    async def get_pending_emails(self, limit: int = 100) -> List[EmailRecord]:
        """Get pending emails that need to be processed."""
        await self._ensure_settings()
        query = f"""
        SELECT 
            batch_id, run_date, agent_name, status, input_file, output_file,
            is_reviewed, review_notes, is_approved, approved_notes, is_email_sent,
            customer_id, contact_id, customer_name, sent_email_id, recipient_email,
            subject, send_timestamp, send_status, error_message, acs_message_id,
            blob_date_folder, json_file_path, html_file_path,
            created_at, updated_at, processed_by
        FROM {self._table_name}
        WHERE agent_name = 'communication' 
            AND status = 'S' 
            AND (is_email_sent IS NULL OR is_email_sent = false)
        ORDER BY run_date ASC, batch_id ASC
        LIMIT {limit}
        """
        
        try:
            results = await self.execute_query(query)
            
            email_records = []
            for row in results:
                # Convert row to EmailRecord
                record = EmailRecord(
                    batch_id=row['batch_id'],
                    run_date=row['run_date'],
                    agent_name=row['agent_name'],
                    status=row['status'],
                    customer_id=row['customer_id'],
                    input_file=row.get('input_file'),
                    output_file=row.get('output_file'),
                    is_reviewed=row.get('is_reviewed'),
                    review_notes=row.get('review_notes'),
                    is_approved=row.get('is_approved'),
                    approved_notes=row.get('approved_notes'),
                    is_email_sent=row.get('is_email_sent'),
                    contact_id=row.get('contact_id'),
                    customer_name=row.get('customer_name'),
                    sent_email_id=row.get('sent_email_id'),
                    recipient_email=row.get('recipient_email'),
                    subject=row.get('subject'),
                    send_timestamp=row.get('send_timestamp'),
                    send_status=row.get('send_status'),
                    error_message=row.get('error_message'),
                    acs_message_id=row.get('acs_message_id'),
                    blob_date_folder=row.get('blob_date_folder'),
                    json_file_path=row.get('json_file_path'),
                    html_file_path=row.get('html_file_path'),
                    created_at=row.get('created_at'),
                    updated_at=row.get('updated_at'),
                    processed_by=row.get('processed_by', 'email_processor')
                )
                email_records.append(record)
            
            logger.info(f"Retrieved {len(email_records)} pending email records")
            return email_records
            
        except Exception as e:
            logger.error("Failed to get pending emails", error=str(e))
            raise
    
    async def update_email_sent(self, batch_id: int, customer_id: str, 
                         sent_email_id: str, recipient_email: str, subject: str,
                         acs_message_id: Optional[str] = None, 
                         send_status: str = "sent") -> bool:
        """Update record after successful email send."""
        await self._ensure_settings()
        try:
            current_time = datetime.now(timezone.utc)
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = true,
                sent_email_id = '{sent_email_id}',
                recipient_email = '{recipient_email}',
                subject = '{subject.replace("'", "''")}',
                send_timestamp = '{current_time.isoformat()}',
                send_status = '{send_status}',
                acs_message_id = '{acs_message_id or ""}',
                updated_at = '{current_time.isoformat()}',
                error_message = NULL
            WHERE batch_id = {batch_id} AND customer_id = '{customer_id}'
            """
            
            affected_rows = await self.execute_update(query)
            
            if affected_rows > 0:
                logger.info(f"Updated email sent status for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No rows updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error("Failed to update email sent status", error=str(e))
            return False
    
    async def update_email_failed(self, batch_id: int, customer_id: str, 
                           error_message: str, attempted_email: Optional[str] = None) -> bool:
        """Update record after failed email send."""
        await self._ensure_settings()
        try:
            current_time = datetime.now(timezone.utc)
            sent_email_id = str(uuid.uuid4())  # Generate ID for tracking even failed attempts
            
            # Escape single quotes in error message
            escaped_error = error_message.replace("'", "''")
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = false,
                sent_email_id = '{sent_email_id}',
                recipient_email = '{attempted_email or ""}',
                send_timestamp = '{current_time.isoformat()}',
                send_status = 'failed',
                error_message = '{escaped_error}',
                updated_at = '{current_time.isoformat()}'
            WHERE batch_id = {batch_id} AND customer_id = '{customer_id}'
            """
            
            affected_rows = await self.execute_update(query)
            
            if affected_rows > 0:
                logger.info(f"Updated email failed status for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No rows updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error("Failed to update email failed status", error=str(e))
            return False
    
    async def get_email_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get email processing statistics for the last N days."""
        await self._ensure_settings()
        query = f"""
        SELECT 
            send_status,
            COUNT(*) as count,
            MIN(send_timestamp) as earliest_send,
            MAX(send_timestamp) as latest_send
        FROM {self._table_name}
        WHERE send_timestamp >= CURRENT_DATE() - INTERVAL {days} DAYS
            AND is_email_sent IS NOT NULL
        GROUP BY send_status
        ORDER BY send_status
        """
        
        try:
            results = await self.execute_query(query)
            
            stats = {
                'total_processed': 0,
                'sent': 0,
                'failed': 0,
                'success_rate': 0.0,
                'period_days': days,
                'details': results
            }
            
            for row in results:
                count = int(row['count'])  # Ensure count is an integer
                stats['total_processed'] += count
                
                if row['send_status'] == 'sent':
                    stats['sent'] = count
                elif row['send_status'] == 'failed':
                    stats['failed'] = count
            
            # Calculate success rate
            if stats['total_processed'] > 0:
                stats['success_rate'] = (stats['sent'] / stats['total_processed']) * 100
            
            logger.info(f"Retrieved email stats for last {days} days: {stats['total_processed']} total, {stats['sent']} sent, {stats['failed']} failed")
            return stats
            
        except Exception as e:
            logger.error("Failed to get email stats", error=str(e))
            return {'error': str(e)}
    
    async def get_communication_records_for_customer(self, batch_id: int, customer_id: str) -> List[EmailRecord]:
        """Get all communication records for a specific customer and batch."""
        await self._ensure_settings()
        query = f"""
        SELECT 
            batch_id, run_date, agent_name, status, input_file, output_file,
            is_reviewed, review_notes, is_approved, approved_notes, is_email_sent,
            customer_id, contact_id, customer_name, sent_email_id, recipient_email,
            subject, send_timestamp, send_status, error_message, acs_message_id,
            blob_date_folder, json_file_path, html_file_path,
            created_at, updated_at, processed_by
        FROM {self._table_name}
        WHERE batch_id = {batch_id} 
            AND customer_id = '{customer_id}' 
            AND agent_name = 'communication'
        ORDER BY created_at ASC
        """
        
        try:
            results = await self.execute_query(query)
            
            email_records = []
            for row in results:
                record = EmailRecord(
                    batch_id=row['batch_id'],
                    run_date=row['run_date'],
                    agent_name=row['agent_name'],
                    status=row['status'],
                    customer_id=row['customer_id'],
                    input_file=row.get('input_file'),
                    output_file=row.get('output_file'),
                    is_reviewed=row.get('is_reviewed'),
                    review_notes=row.get('review_notes'),
                    is_approved=row.get('is_approved'),
                    approved_notes=row.get('approved_notes'),
                    is_email_sent=row.get('is_email_sent'),
                    contact_id=row.get('contact_id'),
                    customer_name=row.get('customer_name'),
                    sent_email_id=row.get('sent_email_id'),
                    recipient_email=row.get('recipient_email'),
                    subject=row.get('subject'),
                    send_timestamp=row.get('send_timestamp'),
                    send_status=row.get('send_status'),
                    error_message=row.get('error_message'),
                    acs_message_id=row.get('acs_message_id'),
                    blob_date_folder=row.get('blob_date_folder'),
                    json_file_path=row.get('json_file_path'),
                    html_file_path=row.get('html_file_path'),
                    created_at=row.get('created_at'),
                    updated_at=row.get('updated_at'),
                    processed_by=row.get('processed_by', 'email_processor')
                )
                email_records.append(record)
            
            logger.debug(f"Retrieved {len(email_records)} communication records for batch_id={batch_id}, customer_id={customer_id}")
            return email_records
            
        except Exception as e:
            logger.error("Failed to get communication records for customer", error=str(e))
            return []
    
    async def update_all_customer_records_sent(self, batch_id: int, customer_id: str, 
                                       sent_email_id: str, recipient_email: str, subject: str,
                                       acs_message_id: Optional[str] = None, 
                                       send_status: str = "sent") -> bool:
        """Update all communication records for a customer after successful email send."""
        await self._ensure_settings()
        try:
            current_time = datetime.now(timezone.utc)
            
            # Escape single quotes in subject
            escaped_subject = subject.replace("'", "''")
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = true,
                sent_email_id = '{sent_email_id}',
                recipient_email = '{recipient_email}',
                subject = '{escaped_subject}',
                send_timestamp = '{current_time.isoformat()}',
                send_status = '{send_status}',
                acs_message_id = '{acs_message_id or ""}',
                updated_at = '{current_time.isoformat()}',
                error_message = NULL
            WHERE batch_id = {batch_id} AND customer_id = '{customer_id}' AND agent_name = 'communication'
            """
            
            affected_rows = await self.execute_update(query)
            
            if affected_rows > 0:
                logger.info(f"Updated communication records for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No communication records updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error("Failed to update all customer records", error=str(e))
            return False
    
    async def update_all_customer_records_failed(self, batch_id: int, customer_id: str, 
                                         error_message: str, attempted_email: Optional[str] = None) -> bool:
        """Update all communication records for a customer after failed email send."""
        await self._ensure_settings()
        try:
            current_time = datetime.now(timezone.utc)
            sent_email_id = str(uuid.uuid4())  # Generate ID for tracking even failed attempts
            
            # Escape single quotes in error message
            escaped_error = error_message.replace("'", "''")
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = false,
                sent_email_id = '{sent_email_id}',
                recipient_email = '{attempted_email or ""}',
                send_timestamp = '{current_time.isoformat()}',
                send_status = 'failed',
                error_message = '{escaped_error}',
                updated_at = '{current_time.isoformat()}'
            WHERE batch_id = {batch_id} AND customer_id = '{customer_id}' AND agent_name = 'communication'
            """
            
            affected_rows = await self.execute_update(query)
            
            if affected_rows > 0:
                logger.info(f"Updated communication records as failed for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No communication records updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error("Failed to update all customer records as failed", error=str(e))
            return False

    async def test_connection(self) -> bool:
        """Test the Databricks OAuth connection."""
        try:
            # Use connection pool to test connectivity
            return await self.execute_with_connection(
                self._test_connection_impl
            )
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            return False
    
    async def _test_connection_impl(self, connection: DatabricksOAuthClient) -> bool:
        """Implementation of connection test with pooled connection."""
        try:
            return await connection.test_connection()
        except Exception as e:
            logger.error("Connection test implementation failed", error=str(e))
            return False