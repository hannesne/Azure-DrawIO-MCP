---
name: update-azure-shapes
description: Updates the Azure DrawIO shape definitions based on all SVG icons available in the jgraph/drawio GitHub repository. Use this when asked to update, refresh, or sync Azure shapes from the DrawIO repository.
license: MIT
---

# Update Azure Shapes from DrawIO Repository

This skill helps you update the `azure_shapes.py` file with the latest Azure icons from the official DrawIO repository.

## When to use this skill

Use this skill when:
- Asked to update or refresh Azure shape definitions
- Need to sync with the latest Azure icons from DrawIO
- Want to add new Azure services that are available in DrawIO
- Need to verify which Azure icons are available

## Process Overview

1. **Fetch icon data** using curl + jq (or Python if jq unavailable)
2. **Analyze** what's new, removed, or changed
3. **Update** azure_shapes.py with proper naming and categorization
4. **Validate** the changes

## Step 1: Analyze Differences

Use the provided analysis script to compare DrawIO repository with current shapes:

```bash
python .github/skills/update-azure-shapes/analyze_icons.py
```

This script will:
- **Check for duplicate keys** in azure_shapes.py (prevents bugs where duplicate keys cause earlier definitions to be invisible)
- Fetch the latest icon list from DrawIO GitHub repository
- Compare with current [azure_drawio_mcp_server/azure_shapes.py](../../../azure_drawio_mcp_server/azure_shapes.py)
- Report new icons available in DrawIO
- Report any icons we reference that no longer exist

**Important:** The script exits with an error if duplicate keys are found, as these cause incorrect reporting of "new" icons. When a key appears twice in the dictionary, only the last definition is kept, making the first one appear as a missing icon.

## Step 2: Analyze and Update azure_shapes.py

Read the current [azure_drawio_mcp_server/azure_shapes.py](../../../azure_drawio_mcp_server/azure_shapes.py) file and:

1. **Extract category and filename** from each path:
   - Path: `src/main/webapp/img/lib/azure2/compute/Virtual_Machine.svg`
   - Category: `compute`
   - Filename: `Virtual_Machine.svg`
   - Relative path for code: `compute/Virtual_Machine.svg`

2. **Generate Python key** (CamelCase with smart singularization):
   - Remove underscores and convert to CamelCase
   - **Singularize resource types** (instances): `Virtual_Machines.svg` → `VirtualMachine`
   - **Preserve service names** that are inherently plural: `Cognitive_Services.svg` → `CognitiveServices`
   - **Examples:**
     - `Subscriptions.svg` → `Subscription` (resource type - singular)
     - `Storage_Accounts.svg` → `StorageAccount` (resource type - singular)
     - `Managed_Identities.svg` → `ManagedIdentity` (resource type - singular)
     - `Container_Instances.svg` → `ContainerInstance` (resource type - singular)
     - `Cognitive_Services.svg` → `CognitiveServices` (official Microsoft service name - plural)
     - `Analysis_Services.svg` → `AnalysisServices` (official Microsoft service name - plural)
     - `Storage_Azure_Files.svg` → `StorageAzureFiles` (official Microsoft service name - plural)

3. **Generate display name** (human-readable):
   - Replace underscores with spaces
   - `Virtual_Machine.svg` → `Virtual Machine`
   - `App_Service_Plans.svg` → `App Service Plans`

4. **Map category** (DrawIO folder → Python category):
   ```python
   {
       'compute': 'compute',
       'containers': 'containers',
       'databases': 'database',        # singular!
       'networking': 'network',         # singular!
       'storage': 'storage',
       'ai_machine_learning': 'ai',
       'analytics': 'analytics',
       'app_services': 'web',
       'devops': 'devops',
       'integration': 'integration',
       'security': 'security',
       'identity': 'identity',
       'iot': 'iot',
       'management_governance': 'management',
       'general': 'general',
       'other': 'other',
       # ... use existing mappings in the file
   }
   ```

5. **Create entry with semantic categorization**:
   ```python
   # Instantiable resources (singular keys)
   'VirtualMachine': ('Virtual Machine', 'compute', 'compute/Virtual_Machine.svg'),
   'Subscription': ('Subscriptions', 'management', 'general/Subscriptions.svg'),
   'ManagedIdentity': ('Managed Identities', 'identity', 'identity/Managed_Identities.svg'),
   'ContainerInstance': ('Container Instances', 'compute', 'compute/Container_Instances.svg'),
   Official Microsoft service names (preserve plural)
   'CognitiveServices': ('Cognitive Services', 'ai', 'ai_machine_learning/Cognitive_Services.svg'),
   'AnalysisServices': ('Analysis Services', 'analytics', 'analytics/Analysis_Services.svg'),
   # Service features (preserve plural only when not a standalone resource)
   'StorageAzureFiles': ('Storage Azure Files', 'storage', 'general/Storage_Azure_Files.svg'),
   ```

### Key Naming Rules

**Singular Keys (Instantiable Resources):**
- Use singular form for most Azure resource types that you can deploy as individual instances
- Examples: `Subscription`, `VirtualMachine`, `StorageAccount`, `ResourceGroup`, `FunctionApp`, `ManagedIdentity`, `ContainerInstance`
- Pattern: If you can create "a [resource]" in Azure portal → use singular
- Test: Can you run `az [service] create --name my-instance`? → singular

**Plural Keys (Official Microsoft Service Names):**
- Preserve plural when it's the official Microsoft service name, regardless of instantiability
- Examples: `CognitiveServices`, `AnalysisServices`, `RecoveryServices`, `StorageAzureFiles`
- Pattern: Use Microsoft's official service name as documented in Azure
- Test: Check Microsoft documentation - if the service is officially "Azure [Name] Services" → keep plural

**Category Overrides:**
- Apply semantic categorization based on function, not just folder location
- Examples:
  - `Spot_VM.svg` in `networking/` → category: `compute`
  - `Storage_Azure_Files.svg` in `general/` → category: `storage`
  - `On_Premises_Data_Gateways.svg` in `general/` → category: `integration`

### Preservation Rules

✅ **Preserve:**
- Existing entries with better custom names
- Common aliases (e.g., both `VM` and `VirtualMachine`)
- Hand-written comments
- Custom categorizations that make more sense

❌ **Remove:**
- Entries for icons that no longer exist in DrawIO
- Duplicates (unless intentional aliases)

⚠️ **Critical - Avoid Duplicate Keys:**
- Never create duplicate dictionary keys
- Each key must appear only once in the AZURE_SHAPES dictionary
- Duplicate keys cause the first definition to be silently overwritten
- The analyze_icons.py script will detect and report duplicates before processing

⚠️ **Merge:**
- Add new icons
- Update paths if changed
- Keep manually-improved names/categories

### Organization

Organize entries by Python category with section headers:

```python
AZURE_SHAPES: Dict[str, Tuple[str, str, Optional[str]]] = {
    # ========== Compute ==========
    'VirtualMachine': ('Virtual Machine', 'compute', 'compute/Virtual_Machine.svg'),
    'BatchAccounts': ('Batch Accounts', 'compute', 'compute/Batch_Accounts.svg'),
    # ...
    
    # ========== Containers ==========
    'KubernetesServices': ('Kubernetes Services', 'containers', 'containers/Kubernetes_Services.svg'),
    # ...
    
    # ========== Network ==========
    'VirtualNetworks': ('Virtual Networks', 'network', 'networking/Virtual_Networks.svg'),
    # ...
}
```

**Category order:** compute, containers, network, storage, database, web, security, identity, integration, ai, analytics, devops, management, iot, mixed_reality, other, general

## Step 3: Validation

After updating, validate:

```bash
# Run the analysis script to check for duplicates
python .github/skills/update-azure-shapes/analyze_icons.py

# Check Python syntax
python3 -m py_compile azure_drawio_mcp_server/azure_shapes.py

# Test import and count
python3 -c "from azure_drawio_mcp_server.azure_shapes import AZURE_SHAPES; print(f'{len(AZURE_SHAPES)} shapes loaded')"

# Test a shape lookup
python3 -c "from azure_drawio_mcp_server.azure_shapes import get_shape_info; print(get_shape_info('VirtualMachine'))"
```

## Example Workflow

**User:** "Update Azure shapes from DrawIO"

**You:**

1. Fetch icons:
   ```bash
   curl -s 'https://api.github.com/repos/jgraph/drawio/git/trees/dev?recursive=1' | \
     jq -r '.tree[].path' | \
     grep 'src/main/webapp/img/lib/azure2/.*\.svg$'
   ```

2. Read current azure_shapes.py

3. Compare to find:
   - New icons to add
   - Removed icons to delete
   - Changed paths to update

4. Update AZURE_SHAPES dictionary with proper formatting

5. Validate changes

6. Report summary:
   ```
   Updated azure_shapes.py:
   - Added: 15 new icons
   - Removed: 2 deprecated icons
   - Updated: 3 paths
   - Total: 648 shapes
   ```

## Common Patterns

```python
# Resource types (singular keys)
'VirtualMachine': ('Virtual Machine', 'compute', 'compute/Virtual_Machine.svg'),
'Subscription': ('Subscriptions', 'management', 'general/Subscriptions.svg'),
'StorageAccount': ('Storage Accounts', 'storage', 'storage/Storage_Accounts.svg'),
'ResourceGroup': ('Resource Groups', 'management', 'general/Resource_Groups.svg'),
'ManagedIdentity': ('Managed Identities', 'identity', 'identity/Managed_Identities.svg'),
'ContainerInstance': ('Container Instances', 'compute', 'compute/Container_Instances.svg'),

# Official Microsoft service names (preserve plural)
'CognitiveServices': ('Cognitive Services', 'ai', 'ai_machine_learning/Cognitive_Services.svg'),
'AnalysisServices': ('Analysis Services', 'analytics', 'analytics/Analysis_Services.svg'),
'RecoveryServicesVault': ('Recovery Services Vaults', 'storage', 'storage/Recovery_Services_Vaults.svg'),
'StorageAzureFiles': ('Storage Azure Files', 'storage', 'general/Storage_Azure_Files.svg'),

# Semantic categorization overrides
'SpotVM': ('Spot VM', 'compute', 'networking/Spot_VM.svg'),  # networking folder → compute category
'ProximityPlacementGroup': ('Proximity Placement Groups', 'compute', 'networking/Proximity_Placement_Groups.svg'),
```
5. Validate changes

6. Report summary:
   ```
   Updated azure_shapes.py:
   - Added: 15 new icons
   - Removed: 2 deprecated icons
   - Updated: 3 paths
   - Total: 648 shapes
   ```

## Common Patterns

```python
# Standard resource
'VirtualMachine': ('Virtual Machine', 'compute', 'compute/Virtual_Machine.svg'),

# Acronym-heavy
'VMSS': ('VM Scale Sets', 'compute', 'compute/VM_Scale_Sets.svg'),

# Long name
'WebApplicationFirewallPolicies': ('Web Application Firewall Policies (WAF)', 'network', 'networking/Web_Application_Firewall_Policies_WAF.svg'),

# Category mapping
'AppServicePlan': ('App Service Plan', 'web', 'app_services/App_Service_Plans.svg'),
```

## Notes

- DrawIO repository: https://github.com/jgraph/drawio
- Icons are on the `dev` branch
- Path prefix: `src/main/webapp/img/lib/azure2/`
- New Azure services are regularly added
- Always review changes before committing
