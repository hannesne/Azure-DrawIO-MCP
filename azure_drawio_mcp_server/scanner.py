# Copyright (c) 2026. Inspired by dminkovski/azure-diagram-mcp
"""Workspace scanner to auto-detect Azure resources from code files.

Supports:
- Bicep files (*.bicep)
- Terraform files (*.tf)
- ARM templates (*.json with ARM schema)
- Azure SDK usage in code (*.cs, *.py, *.js, *.ts)
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredResource:
    """A resource discovered from scanning code."""
    id: str
    resource_type: str
    name: str
    source_file: str
    line_number: Optional[int] = None
    group: Optional[str] = None
    rationale: Optional[str] = None
    connections: List[str] = field(default_factory=list)


# Mapping from Bicep/ARM resource types to our diagram resource types
AZURE_RESOURCE_TYPE_MAP = {
    # Compute
    'microsoft.compute/virtualmachines': 'VM',
    'microsoft.compute/virtualmachinescalesets': 'VMSS',
    'microsoft.web/sites': 'AppService',
    'microsoft.web/serverfarms': 'AppServicePlan',
    'microsoft.containerservice/managedclusters': 'AKS',
    'microsoft.containerinstance/containergroups': 'ContainerInstances',
    'microsoft.containerregistry/registries': 'ACR',
    'microsoft.app/containerapps': 'ContainerApps',
    'microsoft.batch/batchaccounts': 'Batch',
    
    # Functions
    'microsoft.web/sites/functions': 'FunctionApp',
    
    # Networking
    'microsoft.network/virtualnetworks': 'VNet',
    'microsoft.network/virtualnetworks/subnets': 'Subnet',
    'microsoft.network/loadbalancers': 'LoadBalancer',
    'microsoft.network/applicationgateways': 'ApplicationGateway',
    'microsoft.network/frontdoors': 'FrontDoor',
    'microsoft.cdn/profiles': 'CDN',
    'microsoft.network/azurefirewalls': 'Firewall',
    'microsoft.network/virtualnetworkgateways': 'VPNGateway',
    'microsoft.network/expressroutecircuits': 'ExpressRoute',
    'microsoft.network/bastionhosts': 'Bastion',
    'microsoft.network/privatednszones': 'PrivateDNS',
    'microsoft.network/privateendpoints': 'PrivateEndpoint',
    'microsoft.network/networksecuritygroups': 'NSG',
    'microsoft.network/publicipaddresses': 'PublicIP',
    'microsoft.network/trafficmanagerprofiles': 'TrafficManager',
    'microsoft.network/dnszones': 'DNS',
    
    # Storage
    'microsoft.storage/storageaccounts': 'StorageAccount',
    'microsoft.storage/storageaccounts/blobservices': 'BlobStorage',
    'microsoft.storage/storageaccounts/fileservices': 'FileStorage',
    'microsoft.datalakestore/accounts': 'DataLake',
    'microsoft.compute/disks': 'ManagedDisk',
    
    # Databases
    'microsoft.sql/servers': 'SQLServer',
    'microsoft.sql/servers/databases': 'SQLDatabase',
    'microsoft.documentdb/databaseaccounts': 'CosmosDB',
    'microsoft.cache/redis': 'Redis',
    'microsoft.dbformysql/servers': 'MySQL',
    'microsoft.dbformysql/flexibleservers': 'MySQL',
    'microsoft.dbforpostgresql/servers': 'PostgreSQL',
    'microsoft.dbforpostgresql/flexibleservers': 'PostgreSQL',
    'microsoft.synapse/workspaces': 'Synapse',
    
    # Integration
    'microsoft.servicebus/namespaces': 'ServiceBus',
    'microsoft.eventhub/namespaces': 'EventHub',
    'microsoft.eventgrid/topics': 'EventGrid',
    'microsoft.eventgrid/systemtopics': 'EventGrid',
    'microsoft.logic/workflows': 'LogicApp',
    'microsoft.datafactory/factories': 'DataFactory',
    'microsoft.apimanagement/service': 'APIM',
    'microsoft.signalrservice/signalr': 'SignalR',
    
    # Security
    'microsoft.keyvault/vaults': 'KeyVault',
    'microsoft.managedidentity/userassignedidentities': 'ManagedIdentity',
    
    # AI/ML
    'microsoft.cognitiveservices/accounts': 'CognitiveServices',
    'microsoft.machinelearningservices/workspaces': 'MachineLearning',
    'microsoft.search/searchservices': 'AISearch',
    'microsoft.botservice/botservices': 'BotService',
    
    # Analytics
    'microsoft.databricks/workspaces': 'Databricks',
    'microsoft.streamanalytics/streamingjobs': 'StreamAnalytics',
    'microsoft.hdinsight/clusters': 'HDInsight',
    
    # Monitoring
    'microsoft.insights/components': 'ApplicationInsights',
    'microsoft.operationalinsights/workspaces': 'LogAnalytics',
    'microsoft.insights/actiongroups': 'Monitor',
    
    # IoT
    'microsoft.devices/iothubs': 'IoTHub',
    'microsoft.iotcentral/iotapps': 'IoTCentral',
    'microsoft.digitaltwins/digitaltwinsinstances': 'DigitalTwins',
}

# Terraform azurerm resource type mappings
TERRAFORM_RESOURCE_MAP = {
    'azurerm_virtual_machine': 'VM',
    'azurerm_linux_virtual_machine': 'VM',
    'azurerm_windows_virtual_machine': 'VM',
    'azurerm_virtual_machine_scale_set': 'VMSS',
    'azurerm_app_service': 'AppService',
    'azurerm_linux_web_app': 'AppService',
    'azurerm_windows_web_app': 'AppService',
    'azurerm_function_app': 'FunctionApp',
    'azurerm_linux_function_app': 'FunctionApp',
    'azurerm_windows_function_app': 'FunctionApp',
    'azurerm_kubernetes_cluster': 'AKS',
    'azurerm_container_registry': 'ACR',
    'azurerm_container_group': 'ContainerInstances',
    'azurerm_container_app': 'ContainerApps',
    'azurerm_virtual_network': 'VNet',
    'azurerm_subnet': 'Subnet',
    'azurerm_lb': 'LoadBalancer',
    'azurerm_application_gateway': 'ApplicationGateway',
    'azurerm_frontdoor': 'FrontDoor',
    'azurerm_cdn_profile': 'CDN',
    'azurerm_firewall': 'Firewall',
    'azurerm_virtual_network_gateway': 'VPNGateway',
    'azurerm_bastion_host': 'Bastion',
    'azurerm_private_endpoint': 'PrivateEndpoint',
    'azurerm_network_security_group': 'NSG',
    'azurerm_public_ip': 'PublicIP',
    'azurerm_storage_account': 'StorageAccount',
    'azurerm_storage_container': 'BlobStorage',
    'azurerm_storage_share': 'FileStorage',
    'azurerm_mssql_server': 'SQLServer',
    'azurerm_mssql_database': 'SQLDatabase',
    'azurerm_sql_server': 'SQLServer',
    'azurerm_sql_database': 'SQLDatabase',
    'azurerm_cosmosdb_account': 'CosmosDB',
    'azurerm_redis_cache': 'Redis',
    'azurerm_mysql_server': 'MySQL',
    'azurerm_mysql_flexible_server': 'MySQL',
    'azurerm_postgresql_server': 'PostgreSQL',
    'azurerm_postgresql_flexible_server': 'PostgreSQL',
    'azurerm_servicebus_namespace': 'ServiceBus',
    'azurerm_eventhub_namespace': 'EventHub',
    'azurerm_eventgrid_topic': 'EventGrid',
    'azurerm_logic_app_workflow': 'LogicApp',
    'azurerm_data_factory': 'DataFactory',
    'azurerm_api_management': 'APIM',
    'azurerm_signalr_service': 'SignalR',
    'azurerm_key_vault': 'KeyVault',
    'azurerm_user_assigned_identity': 'ManagedIdentity',
    'azurerm_cognitive_account': 'CognitiveServices',
    'azurerm_machine_learning_workspace': 'MachineLearning',
    'azurerm_search_service': 'AISearch',
    'azurerm_databricks_workspace': 'Databricks',
    'azurerm_stream_analytics_job': 'StreamAnalytics',
    'azurerm_application_insights': 'ApplicationInsights',
    'azurerm_log_analytics_workspace': 'LogAnalytics',
    'azurerm_iothub': 'IoTHub',
    'azurerm_synapse_workspace': 'Synapse',
}

# Azure SDK patterns for detecting resources in code
SDK_PATTERNS = {
    # .NET Azure SDK
    r'BlobServiceClient|BlobContainerClient': 'BlobStorage',
    r'CosmosClient|CosmosDatabase': 'CosmosDB',
    r'KeyVaultClient|SecretClient|KeyClient': 'KeyVault',
    r'ServiceBusClient|ServiceBusSender': 'ServiceBus',
    r'EventHubProducerClient|EventHubConsumerClient': 'EventHub',
    r'SearchClient|SearchIndexClient': 'AISearch',
    r'OpenAIClient|ChatCompletionsClient': 'AzureOpenAI',
    r'SqlConnection.*\.database\.windows\.net': 'SQLDatabase',
    r'RedisConnection|StackExchange\.Redis': 'Redis',
    r'TableServiceClient|TableClient': 'TableStorage',
    r'QueueServiceClient|QueueClient': 'QueueStorage',
    
    # Python Azure SDK
    r'BlobServiceClient|ContainerClient': 'BlobStorage',
    r'CosmosClient': 'CosmosDB',
    r'SecretClient|KeyClient|CertificateClient': 'KeyVault',
    r'ServiceBusClient': 'ServiceBus',
    r'EventHubProducerClient|EventHubConsumerClient': 'EventHub',
    r'SearchClient': 'AISearch',
    r'AzureOpenAI|AsyncAzureOpenAI': 'AzureOpenAI',
    
    # Connection strings
    r'AccountName=\w+;.*BlobEndpoint': 'StorageAccount',
    r'\.blob\.core\.windows\.net': 'BlobStorage',
    r'\.table\.core\.windows\.net': 'TableStorage',
    r'\.queue\.core\.windows\.net': 'QueueStorage',
    r'\.servicebus\.windows\.net': 'ServiceBus',
    r'\.documents\.azure\.com': 'CosmosDB',
    r'\.vault\.azure\.net': 'KeyVault',
    r'\.database\.windows\.net': 'SQLDatabase',
    r'\.redis\.cache\.windows\.net': 'Redis',
    r'\.search\.windows\.net': 'AISearch',
    r'\.openai\.azure\.com': 'AzureOpenAI',
    r'\.cognitiveservices\.azure\.com': 'CognitiveServices',
    r'\.signalr\.net': 'SignalR',
    r'\.azurewebsites\.net': 'AppService',
    r'\.azurecr\.io': 'ACR',
}


class WorkspaceScanner:
    """Scans a workspace directory for Azure resources."""
    
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.resources: Dict[str, DiscoveredResource] = {}
        self.connections: List[Tuple[str, str, str]] = []  # (source, target, label)
        self._resource_counter = 0
    
    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID for a resource."""
        self._resource_counter += 1
        return f"{prefix}_{self._resource_counter}"
    
    def _add_resource(
        self,
        resource_type: str,
        name: str,
        source_file: str,
        line_number: Optional[int] = None,
        group: Optional[str] = None,
    ) -> str:
        """Add a discovered resource and return its ID."""
        # Check for duplicates by name and type
        for res_id, res in self.resources.items():
            if res.name == name and res.resource_type == resource_type:
                return res_id
        
        res_id = self._generate_id(resource_type.lower())
        rel_path = str(Path(source_file).relative_to(self.workspace_dir))
        
        self.resources[res_id] = DiscoveredResource(
            id=res_id,
            resource_type=resource_type,
            name=name,
            source_file=rel_path,
            line_number=line_number,
            group=group,
            rationale=f"Discovered in {rel_path}" + (f":{line_number}" if line_number else ""),
        )
        return res_id
    
    def scan(self) -> Tuple[List[DiscoveredResource], List[Tuple[str, str, str]]]:
        """
        Scan the workspace for Azure resources.
        
        Returns:
            Tuple of (resources, connections)
        """
        if not self.workspace_dir.exists():
            logger.warning(f"Workspace directory does not exist: {self.workspace_dir}")
            return [], []
        
        # Scan different file types
        self._scan_bicep_files()
        self._scan_terraform_files()
        self._scan_arm_templates()
        self._scan_code_files()
        
        # Infer connections based on common patterns
        self._infer_connections()
        
        return list(self.resources.values()), self.connections
    
    def _scan_bicep_files(self) -> None:
        """Scan Bicep files for resource definitions."""
        for bicep_file in self.workspace_dir.rglob('*.bicep'):
            if self._should_skip(bicep_file):
                continue
            
            try:
                content = bicep_file.read_text(encoding='utf-8')
                self._parse_bicep(content, str(bicep_file))
            except Exception as e:
                logger.warning(f"Error parsing Bicep file {bicep_file}: {e}")
    
    def _parse_bicep(self, content: str, file_path: str) -> None:
        """Parse Bicep content for resource definitions."""
        # Match resource declarations: resource <name> '<type>@<version>' = {
        resource_pattern = r"resource\s+(\w+)\s+'([^']+)@[^']+'\s*="
        
        for match in re.finditer(resource_pattern, content, re.MULTILINE):
            bicep_name = match.group(1)
            resource_type = match.group(2).lower()
            line_num = content[:match.start()].count('\n') + 1
            
            if resource_type in AZURE_RESOURCE_TYPE_MAP:
                diagram_type = AZURE_RESOURCE_TYPE_MAP[resource_type]
                # Try to extract a display name from the resource definition
                name = self._extract_bicep_name(content, match.end(), bicep_name)
                self._add_resource(diagram_type, name, file_path, line_num)
    
    def _extract_bicep_name(self, content: str, start_pos: int, fallback: str) -> str:
        """Extract the name property from a Bicep resource definition."""
        # Look for name: '...' or name: concat(...) within the next 500 chars
        search_region = content[start_pos:start_pos + 500]
        name_match = re.search(r"name:\s*'([^']+)'", search_region)
        if name_match:
            return name_match.group(1)
        return fallback.replace('_', ' ').title()
    
    def _scan_terraform_files(self) -> None:
        """Scan Terraform files for Azure resource definitions."""
        for tf_file in self.workspace_dir.rglob('*.tf'):
            if self._should_skip(tf_file):
                continue
            
            try:
                content = tf_file.read_text(encoding='utf-8')
                self._parse_terraform(content, str(tf_file))
            except Exception as e:
                logger.warning(f"Error parsing Terraform file {tf_file}: {e}")
    
    def _parse_terraform(self, content: str, file_path: str) -> None:
        """Parse Terraform content for azurerm resource definitions."""
        # Match resource blocks: resource "azurerm_xxx" "name" {
        resource_pattern = r'resource\s+"(azurerm_\w+)"\s+"(\w+)"\s*\{'
        
        for match in re.finditer(resource_pattern, content, re.MULTILINE):
            tf_type = match.group(1)
            tf_name = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            
            if tf_type in TERRAFORM_RESOURCE_MAP:
                diagram_type = TERRAFORM_RESOURCE_MAP[tf_type]
                # Try to extract the name property
                name = self._extract_tf_name(content, match.end(), tf_name)
                self._add_resource(diagram_type, name, file_path, line_num)
    
    def _extract_tf_name(self, content: str, start_pos: int, fallback: str) -> str:
        """Extract the name property from a Terraform resource block."""
        # Find the closing brace for this resource
        search_region = content[start_pos:start_pos + 1000]
        name_match = re.search(r'name\s*=\s*"([^"]+)"', search_region)
        if name_match:
            # Handle interpolation ${...}
            name = name_match.group(1)
            if '${' not in name:
                return name
        return fallback.replace('_', ' ').title()
    
    def _scan_arm_templates(self) -> None:
        """Scan ARM template JSON files for resource definitions."""
        for json_file in self.workspace_dir.rglob('*.json'):
            if self._should_skip(json_file):
                continue
            
            try:
                content = json_file.read_text(encoding='utf-8')
                # Check if it's an ARM template
                if '"$schema"' in content and 'deploymentTemplate' in content.lower():
                    data = json.loads(content)
                    self._parse_arm_template(data, str(json_file))
            except json.JSONDecodeError:
                pass  # Not valid JSON, skip
            except Exception as e:
                logger.warning(f"Error parsing ARM template {json_file}: {e}")
    
    def _parse_arm_template(self, data: dict, file_path: str) -> None:
        """Parse ARM template JSON for resources."""
        resources = data.get('resources', [])
        
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            
            resource_type = resource.get('type', '').lower()
            name = resource.get('name', 'Unknown')
            
            # Handle ARM template expressions [...]
            if isinstance(name, str) and name.startswith('['):
                name = resource_type.split('/')[-1].replace('_', ' ').title()
            
            if resource_type in AZURE_RESOURCE_TYPE_MAP:
                diagram_type = AZURE_RESOURCE_TYPE_MAP[resource_type]
                self._add_resource(diagram_type, name, file_path)
            
            # Recursively check nested resources
            nested = resource.get('resources', [])
            if nested:
                self._parse_arm_template({'resources': nested}, file_path)
    
    def _scan_code_files(self) -> None:
        """Scan code files for Azure SDK usage patterns."""
        code_extensions = {'.cs', '.py', '.js', '.ts', '.java'}
        
        for ext in code_extensions:
            for code_file in self.workspace_dir.rglob(f'*{ext}'):
                if self._should_skip(code_file):
                    continue
                
                try:
                    content = code_file.read_text(encoding='utf-8')
                    self._parse_code_file(content, str(code_file))
                except Exception as e:
                    logger.debug(f"Error parsing code file {code_file}: {e}")
    
    def _parse_code_file(self, content: str, file_path: str) -> None:
        """Parse code file for Azure SDK usage patterns."""
        detected_types: Set[str] = set()
        
        for pattern, resource_type in SDK_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                detected_types.add(resource_type)
        
        for resource_type in detected_types:
            name = f"{resource_type} (from code)"
            self._add_resource(resource_type, name, file_path)
    
    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped (node_modules, .git, etc.)."""
        skip_dirs = {
            'node_modules', '.git', '.venv', 'venv', '__pycache__',
            'bin', 'obj', 'dist', 'build', '.terraform', '.next',
        }
        return any(part in skip_dirs for part in path.parts)
    
    def _infer_connections(self) -> None:
        """Infer connections between resources based on common patterns."""
        resource_list = list(self.resources.values())
        
        # Common connection patterns
        connection_rules = [
            # (source_type, target_type, label)
            ('AppService', 'SQLDatabase', 'Database'),
            ('AppService', 'CosmosDB', 'Database'),
            ('AppService', 'Redis', 'Cache'),
            ('AppService', 'KeyVault', 'Secrets'),
            ('AppService', 'StorageAccount', 'Storage'),
            ('AppService', 'BlobStorage', 'Blobs'),
            ('AppService', 'ApplicationInsights', 'Telemetry'),
            ('FunctionApp', 'SQLDatabase', 'Database'),
            ('FunctionApp', 'CosmosDB', 'Database'),
            ('FunctionApp', 'KeyVault', 'Secrets'),
            ('FunctionApp', 'StorageAccount', 'Storage'),
            ('FunctionApp', 'ServiceBus', 'Messages'),
            ('FunctionApp', 'EventHub', 'Events'),
            ('FunctionApp', 'EventGrid', 'Events'),
            ('FunctionApp', 'ApplicationInsights', 'Telemetry'),
            ('AKS', 'ACR', 'Pull Images'),
            ('AKS', 'KeyVault', 'Secrets'),
            ('AKS', 'SQLDatabase', 'Database'),
            ('AKS', 'CosmosDB', 'Database'),
            ('AKS', 'ApplicationInsights', 'Telemetry'),
            ('APIM', 'AppService', 'Backend'),
            ('APIM', 'FunctionApp', 'Backend'),
            ('APIM', 'AKS', 'Backend'),
            ('ApplicationGateway', 'AppService', 'Route'),
            ('ApplicationGateway', 'AKS', 'Route'),
            ('FrontDoor', 'AppService', 'Origin'),
            ('FrontDoor', 'ApplicationGateway', 'Origin'),
            ('LoadBalancer', 'VM', 'Balance'),
            ('LoadBalancer', 'VMSS', 'Balance'),
            ('PrivateEndpoint', 'SQLDatabase', 'Private Link'),
            ('PrivateEndpoint', 'StorageAccount', 'Private Link'),
            ('PrivateEndpoint', 'KeyVault', 'Private Link'),
            ('PrivateEndpoint', 'CosmosDB', 'Private Link'),
            ('LogicApp', 'ServiceBus', 'Messages'),
            ('LogicApp', 'EventGrid', 'Events'),
            ('DataFactory', 'SQLDatabase', 'Source/Sink'),
            ('DataFactory', 'BlobStorage', 'Source/Sink'),
            ('DataFactory', 'Synapse', 'Analytics'),
            ('StreamAnalytics', 'EventHub', 'Input'),
            ('StreamAnalytics', 'IoTHub', 'Input'),
            ('StreamAnalytics', 'CosmosDB', 'Output'),
            ('StreamAnalytics', 'SQLDatabase', 'Output'),
        ]
        
        # Build type-to-resources lookup
        type_lookup: Dict[str, List[str]] = {}
        for res_id, res in self.resources.items():
            if res.resource_type not in type_lookup:
                type_lookup[res.resource_type] = []
            type_lookup[res.resource_type].append(res_id)
        
        # Apply connection rules
        for source_type, target_type, label in connection_rules:
            if source_type in type_lookup and target_type in type_lookup:
                for source_id in type_lookup[source_type]:
                    for target_id in type_lookup[target_type]:
                        self.connections.append((source_id, target_id, label))


async def scan_workspace(
    workspace_dir: str,
) -> Tuple[List[DiscoveredResource], List[Tuple[str, str, str]]]:
    """
    Scan a workspace directory for Azure resources.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Tuple of (discovered_resources, inferred_connections)
    """
    scanner = WorkspaceScanner(workspace_dir)
    return scanner.scan()
