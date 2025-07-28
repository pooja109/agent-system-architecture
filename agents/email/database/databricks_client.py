import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import uuid

from databricks import sql
from databricks.sql.client import Connection, Cursor

from config.settings import DatabricksSettings
from database.models import EmailRecord

logger = logging.getLogger(__name__)

class DatabricksClient:
    """Client for interacting with Databricks SQL Warehouse."""
    
    def __init__(self, settings: DatabricksSettings):
        """Initialize Databricks client with settings."""
        self.settings = settings
        self.connection: Optional[Connection] = None
        self._table_name = f"`{settings.catalog}`.`{settings.schema}`.`email_communication_pipeline{settings.table_suffix}`"
        
    def connect(self) -> bool:
        """Establish connection to Databricks."""
        try:
            self.connection = sql.connect(
                server_hostname=self.settings.server_hostname,
                http_path=self.settings.http_path,
                access_token=self.settings.access_token
            )
            logger.info("Successfully connected to Databricks")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Databricks: {e}")
            return False
    
    def disconnect(self):
        """Close Databricks connection."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Disconnected from Databricks")
            except Exception as e:
                logger.error(f"Error disconnecting from Databricks: {e}")
            finally:
                self.connection = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def execute_query(self, query: str, parameters: Optional[List] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        if not self.connection:
            raise RuntimeError("Not connected to Databricks. Call connect() first.")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, parameters or [])
                
                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Fetch all rows
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                results = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    results.append(row_dict)
                
                logger.debug(f"Query executed successfully, returned {len(results)} rows")
                return results
                
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    def execute_update(self, query: str, parameters: Optional[List] = None) -> int:
        """Execute an update/insert/delete query and return affected row count.
        
        Note: Databricks SQL connector may return -1 for rowcount on UPDATE statements.
        This method returns 1 to indicate successful execution if no exception occurs.
        """
        if not self.connection:
            raise RuntimeError("Not connected to Databricks. Call connect() first.")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, parameters or [])
                
                # Databricks SQL connector often returns -1 for UPDATE statements
                # If no exception occurred, assume the update was successful
                affected_rows = cursor.rowcount
                
                if affected_rows == -1:
                    # Databricks limitation - assume success if no exception
                    logger.debug(f"Update query executed (Databricks returned -1 rowcount, assuming success)")
                    return 1  # Return 1 to indicate successful execution
                else:
                    logger.debug(f"Update query executed successfully, affected {affected_rows} rows")
                    return affected_rows
                
        except Exception as e:
            logger.error(f"Error executing update query: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    def create_tables(self) -> bool:
        """Create the email communication pipeline table and related objects."""
        try:
            # Read the schema SQL file
            import os
            schema_file = os.path.join(os.path.dirname(__file__), 'table_schema.sql')
            
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Replace placeholders with actual values
            schema_sql = schema_sql.format(
                catalog=self.settings.catalog,
                schema=self.settings.schema,
                table_suffix=self.settings.table_suffix
            )
            
            # Split into individual statements
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            # Execute each statement
            for statement in statements:
                if statement:
                    self.execute_update(statement)
                    logger.info(f"Executed: {statement[:50]}...")
            
            logger.info("Successfully created tables and views")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return False
    
    def get_pending_emails(self, limit: int = 100) -> List[EmailRecord]:
        """Get pending emails that need to be processed."""
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
            results = self.execute_query(query)
            
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
            logger.error(f"Failed to get pending emails: {e}")
            raise
    
    def update_email_sent(self, batch_id: int, customer_id: str, 
                         sent_email_id: str, recipient_email: str, subject: str,
                         acs_message_id: Optional[str] = None, 
                         send_status: str = "sent") -> bool:
        """Update record after successful email send."""
        try:
            current_time = datetime.now(timezone.utc)
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = true,
                sent_email_id = ?,
                recipient_email = ?,
                subject = ?,
                send_timestamp = ?,
                send_status = ?,
                acs_message_id = ?,
                updated_at = ?,
                error_message = NULL
            WHERE batch_id = ? AND customer_id = ?
            """
            
            parameters = [
                sent_email_id,
                recipient_email, 
                subject,
                current_time,
                send_status,
                acs_message_id,
                current_time,
                batch_id,
                customer_id
            ]
            
            affected_rows = self.execute_update(query, parameters)
            
            if affected_rows > 0:
                logger.info(f"Updated email sent status for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No rows updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update email sent status: {e}")
            return False
    
    def update_email_failed(self, batch_id: int, customer_id: str, 
                           error_message: str, attempted_email: Optional[str] = None) -> bool:
        """Update record after failed email send."""
        try:
            current_time = datetime.now(timezone.utc)
            sent_email_id = str(uuid.uuid4())  # Generate ID for tracking even failed attempts
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = false,
                sent_email_id = ?,
                recipient_email = ?,
                send_timestamp = ?,
                send_status = 'failed',
                error_message = ?,
                updated_at = ?
            WHERE batch_id = ? AND customer_id = ?
            """
            
            parameters = [
                sent_email_id,
                attempted_email,
                current_time,
                error_message,
                current_time,
                batch_id,
                customer_id
            ]
            
            affected_rows = self.execute_update(query, parameters)
            
            if affected_rows > 0:
                logger.info(f"Updated email failed status for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No rows updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update email failed status: {e}")
            return False
    
    def get_email_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get email processing statistics for the last N days."""
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
            results = self.execute_query(query)
            
            stats = {
                'total_processed': 0,
                'sent': 0,
                'failed': 0,
                'success_rate': 0.0,
                'period_days': days,
                'details': results
            }
            
            for row in results:
                count = row['count']
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
            logger.error(f"Failed to get email stats: {e}")
            return {'error': str(e)}
    
    def get_communication_records_for_customer(self, batch_id: int, customer_id: str) -> List[EmailRecord]:
        """Get all communication records for a specific customer and batch."""
        query = f"""
        SELECT 
            batch_id, run_date, agent_name, status, input_file, output_file,
            is_reviewed, review_notes, is_approved, approved_notes, is_email_sent,
            customer_id, contact_id, customer_name, sent_email_id, recipient_email,
            subject, send_timestamp, send_status, error_message, acs_message_id,
            blob_date_folder, json_file_path, html_file_path,
            created_at, updated_at, processed_by
        FROM {self._table_name}
        WHERE batch_id = ? 
            AND customer_id = ? 
            AND agent_name = 'communication'
        ORDER BY created_at ASC
        """
        
        try:
            results = self.execute_query(query, [batch_id, customer_id])
            
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
            logger.error(f"Failed to get communication records for customer: {e}")
            return []
    
    def update_all_customer_records_sent(self, batch_id: int, customer_id: str, 
                                       sent_email_id: str, recipient_email: str, subject: str,
                                       acs_message_id: Optional[str] = None, 
                                       send_status: str = "sent") -> bool:
        """Update all communication records for a customer after successful email send."""
        try:
            current_time = datetime.now(timezone.utc)
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = true,
                sent_email_id = ?,
                recipient_email = ?,
                subject = ?,
                send_timestamp = ?,
                send_status = ?,
                acs_message_id = ?,
                updated_at = ?,
                error_message = NULL
            WHERE batch_id = ? AND customer_id = ? AND agent_name = 'communication'
            """
            
            parameters = [
                sent_email_id,
                recipient_email, 
                subject,
                current_time.isoformat(),
                send_status,
                acs_message_id,
                current_time.isoformat(),
                batch_id,
                str(customer_id)
            ]
            
            affected_rows = self.execute_update(query, parameters)
            
            if affected_rows > 0:
                logger.info(f"Updated communication records for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No communication records updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update all customer records: {e}")
            return False
    
    def update_all_customer_records_failed(self, batch_id: int, customer_id: str, 
                                         error_message: str, attempted_email: Optional[str] = None) -> bool:
        """Update all communication records for a customer after failed email send."""
        try:
            current_time = datetime.now(timezone.utc)
            sent_email_id = str(uuid.uuid4())  # Generate ID for tracking even failed attempts
            
            query = f"""
            UPDATE {self._table_name}
            SET 
                is_email_sent = false,
                sent_email_id = ?,
                recipient_email = ?,
                send_timestamp = ?,
                send_status = 'failed',
                error_message = ?,
                updated_at = ?
            WHERE batch_id = ? AND customer_id = ? AND agent_name = 'communication'
            """
            
            parameters = [
                sent_email_id,
                attempted_email,
                current_time.isoformat(),
                error_message,
                current_time.isoformat(),
                batch_id,
                str(customer_id)
            ]
            
            affected_rows = self.execute_update(query, parameters)
            
            if affected_rows > 0:
                logger.info(f"Updated communication records as failed for batch_id={batch_id}, customer_id={customer_id}")
                return True
            else:
                logger.warning(f"No communication records updated for batch_id={batch_id}, customer_id={customer_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update all customer records as failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test the Databricks connection."""
        try:
            query = "SELECT 1 as test"
            result = self.execute_query(query)
            return len(result) == 1 and result[0]['test'] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False