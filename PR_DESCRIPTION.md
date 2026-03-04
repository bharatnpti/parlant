# 🚀 Add Azure AD Authentication Support to Azure OpenAI Service

## 📋 Summary

This PR adds comprehensive Azure AD authentication support to the Azure OpenAI service, enabling secure authentication using Azure Active Directory credentials while maintaining full backward compatibility with existing API key authentication.

## ✨ Features Added

### 🔐 **Azure AD Authentication Support**
- **DefaultAzureCredential** integration with proper token scope handling
- Support for multiple Azure AD authentication methods:
  - Azure CLI (`az login`)
  - Service Principal (environment variables)
  - Managed Identity (Azure resources)
  - Environment Credential
  - Workload Identity (Kubernetes)

### 🛡️ **Enhanced Security**
- Proper token scope usage: `https://cognitiveservices.azure.com/.default`
- Secure token provider implementation with error handling
- Comprehensive authentication validation

### 🔄 **Backward Compatibility**
- API key authentication remains fully functional
- Priority system: API key takes precedence over Azure AD
- No breaking changes to existing configurations

### 🧪 **Comprehensive Testing**
- **27 test cases** covering all authentication scenarios
- Mock-based testing for reliable CI/CD
- Integration tests for service factory methods
- Error handling and edge case coverage

## 🔧 Technical Implementation

### **Authentication Flow**
```
AZURE_ENDPOINT exists?
├── No → ❌ Error (required)
└── Yes → AZURE_API_KEY exists?
    ├── Yes → ✅ Use API Key (priority)
    └── No → Try Azure AD
        ├── Success → ✅ Use Azure AD
        └── Failure → ❌ Error with guidance
```

### **Key Changes**

#### **`src/parlant/adapters/nlp/azure_service.py`**
- Enhanced `create_azure_client()` with Azure AD support
- Improved `verify_environment()` with comprehensive authentication detection
- Added proper error handling with helpful user guidance
- Centralized authentication logic for all embedder classes

#### **`tests/adapters/nlp/test_azure_service.py`** (New)
- Complete test suite with 27 test cases
- Mock-based testing for reliable execution
- Coverage of all authentication scenarios
- Error handling validation

## 📚 Usage Examples

### **Azure AD Authentication (Recommended)**

#### **Development (Azure CLI)**
```bash
# Authenticate with Azure CLI
az login

# Set only the endpoint
export AZURE_ENDPOINT="https://your-resource.openai.azure.com/"
```

#### **Production (Service Principal)**
```bash
export AZURE_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
```

#### **Azure Resources (Managed Identity)**
```bash
# Just set the endpoint - managed identity is automatic
export AZURE_ENDPOINT="https://your-resource.openai.azure.com/"
```

### **Legacy API Key Authentication**
```bash
export AZURE_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_API_KEY="your-api-key"
```

## 🎯 Benefits

### **Security Improvements**
- ✅ Eliminates need to store API keys in environment variables
- ✅ Uses Azure's secure token-based authentication
- ✅ Supports role-based access control (RBAC)
- ✅ Automatic token refresh and management

### **Operational Benefits**
- ✅ Simplified deployment in Azure environments
- ✅ Better integration with Azure DevOps and CI/CD
- ✅ Support for Azure Key Vault integration
- ✅ Enhanced audit logging and compliance

### **Developer Experience**
- ✅ Clear error messages with troubleshooting guidance
- ✅ Comprehensive documentation in error messages
- ✅ Seamless fallback to API key authentication
- ✅ No breaking changes to existing code

## 🧪 Testing

### **Test Coverage**
- ✅ **27 test cases** covering all scenarios
- ✅ Authentication method detection
- ✅ Client creation with proper credentials
- ✅ Error handling and user guidance
- ✅ Environment variable validation
- ✅ Service integration testing

### **Test Results**
```bash
$ python -m pytest tests/adapters/nlp/test_azure_service.py -v
========================================= 27 passed in 0.55s =========================================
```

## 📖 Documentation

### **Error Messages**
The implementation provides comprehensive error messages with:
- Clear setup instructions
- Multiple authentication method options
- Links to official Microsoft documentation
- Role requirements (`Cognitive Services OpenAI User`)

### **Environment Variables**
- **Required**: `AZURE_ENDPOINT`
- **Optional**: `AZURE_API_KEY` (legacy)
- **Azure AD**: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`

## 🔍 Code Quality

### **Linting**
- ✅ No linting errors
- ✅ Follows project coding standards
- ✅ Proper type hints and documentation

### **Architecture**
- ✅ Centralized authentication logic
- ✅ Clean separation of concerns
- ✅ Proper error handling and logging
- ✅ Maintainable and extensible design

## 🚀 Migration Guide

### **For Existing Users**
No changes required! Existing API key authentication continues to work exactly as before.

### **For New Azure AD Users**
1. Remove `AZURE_API_KEY` from environment
2. Authenticate with Azure AD using one of the supported methods
3. Set `AZURE_ENDPOINT`
4. Ensure your identity has the `Cognitive Services OpenAI User` role

## 📝 Changelog

### **Added**
- Azure AD authentication support to Azure OpenAI service
- Comprehensive test suite for Azure authentication functionality
- Support for DefaultAzureCredential with proper token scope handling
- Detailed error messages and troubleshooting guidance for Azure AD authentication

### **Changed**
- Enhanced Azure service to support both legacy API key and Azure AD authentication
- Improved Azure service environment verification with better error handling
- Updated Azure embedder classes to use centralized authentication logic

### **Fixed**
- Azure AD token provider to use correct scope for Azure OpenAI services
- Authentication error handling with helpful user guidance

## 🔗 Related Issues

This enhancement addresses the need for secure Azure AD authentication in enterprise environments while maintaining backward compatibility.

## ✅ Checklist

- [x] Code follows project style guidelines
- [x] Self-review completed
- [x] Tests added/updated and passing
- [x] Documentation updated
- [x] No breaking changes
- [x] Backward compatibility maintained
- [x] Error handling implemented
- [x] Comprehensive test coverage
- [x] DCO sign-off included

---

**Ready for review! 🎉**
