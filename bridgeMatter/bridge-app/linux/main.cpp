/*
 *  Modified for: single-light Matter bridge relaying On/Off to a cloud API
 *  POC uses system("curl ...") to avoid build changes. Switch to libcurl later if needed.
 */

#include <AppMain.h>
#include <cstdint>
#include <platform/CHIPDeviceLayer.h>
#include <platform/PlatformManager.h>

#include <app-common/zap-generated/ids/Attributes.h>
#include <app-common/zap-generated/ids/Clusters.h>
#include <app/AttributeAccessInterfaceRegistry.h>
#include <app/ConcreteAttributePath.h>
#include <app/EventLogging.h>
#include <app/reporting/reporting.h>
#include <app/util/af-types.h>
#include <app/util/attribute-storage.h>
#include <app/util/endpoint-config-api.h>
#include <app/util/util.h>
#include <credentials/DeviceAttestationCredsProvider.h>
#include <credentials/examples/DeviceAttestationCredsExample.h>
#include <lib/core/CHIPError.h>
#include <lib/support/CHIPMem.h>
#include <lib/support/ZclString.h>
#include <platform/CommissionableDataProvider.h>
#include <setup_payload/QRCodeSetupPayloadGenerator.h>
#include <setup_payload/SetupPayload.h>

#include <app/server/Server.h>

#include <cassert>
#include <iostream>
#include <string>
#include <vector>

// ======== POC HTTP relay helpers (ADD) ========
#include <cstdlib>   // system()
#include <sstream>   // ostringstream

using namespace chip;
using namespace chip::app;
using namespace chip::Credentials;
using namespace chip::Inet;
using namespace chip::Transport;
using namespace chip::DeviceLayer;
using namespace chip::app::Clusters;

// ----------- HTTP relay helpers (ADD) -----------
static std::string mapEndpointToDeviceId(chip::EndpointId /*ep*/)
{
    // Single bulb only -> map to your cloud's bulb id if you use one.
    // For your Flask API you don't need an ID in the path; we will call /cloud/on and /cloud/off directly.
    return "bulb-001";
}

// Basic shell-out curl wrapper for POST without body
static void httpPostNoBody(const std::string & url, const char * apiKeyOpt = nullptr)
{
    std::ostringstream cmd;
    cmd << "curl -s -X POST \"" << url << "\" -H 'Content-Type: application/json'";
    if (apiKeyOpt && std::string(apiKeyOpt).size() > 0)
    {
        cmd << " -H 'Authorization: Bearer " << apiKeyOpt << "'";
    }
    int rc = std::system(cmd.str().c_str());
    if (rc != 0)
    {
        ChipLogError(NotSpecified, "[HTTP] POST failed rc=%d url=%s", rc, url.c_str());
    }
    else
    {
        ChipLogProgress(NotSpecified, "[HTTP] POST OK url=%s", url.c_str());
    }
}

// Relay On/Off to your Flask cloud (/cloud/on, /cloud/off)
static void postToCloudOnOff(bool on, chip::EndpointId ep)
{
    const char * baseUrl = std::getenv("CLOUD_BASE_URL"); // e.g., http://127.0.0.1:6000
    const char * apiKey  = std::getenv("CLOUD_API_KEY");  // optional

    if (!baseUrl)
    {
        ChipLogError(NotSpecified, "[HTTP] CLOUD_BASE_URL not set (export CLOUD_BASE_URL=http://host:6000)");
        return;
    }

    // Your Flask API expects: POST /cloud/on  OR  POST /cloud/off  (no body required)
    std::string url = std::string(baseUrl) + (on ? "/cloud/on" : "/cloud/off");

    ChipLogProgress(NotSpecified, "[HTTP] Relay ep=%u -> %s", static_cast<unsigned>(ep), url.c_str());
    httpPostNoBody(url, apiKey);
}
// -----------------------------------------------

// These variables need to be in global scope for bridged-actions-stub.cpp to access them
std::vector<Room *> gRooms;
std::vector<Action *> gActions;

namespace {

NamedPipeCommands sChipNamedPipeCommands;
BridgeCommandDelegate sBridgeCommandDelegate;

const int kNodeLabelSize = 32;
const int kUniqueIdSize  = 32;
// Current ZCL implementation of Struct uses a max-size array of 254 bytes
const int kDescriptorAttributeArraySize = 254;

EndpointId gCurrentEndpointId;
EndpointId gFirstDynamicEndpointId;
// Power source is on the same endpoint as the composed device
Device * gDevices[CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT + 1];

const int16_t minMeasuredValue     = -27315;
const int16_t maxMeasuredValue     = 32766;
const int16_t initialMeasuredValue = 100;

// Device types for dynamic endpoints:
#define DEVICE_TYPE_BRIDGED_NODE 0x0013
#define DEVICE_TYPE_LO_ON_OFF_LIGHT 0x0100
#define DEVICE_VERSION_DEFAULT 1

// -------- Light endpoint clusters (we keep ONLY OnOff + Descriptor + BridgedDeviceBasic) --------

// On/Off attributes
DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(onOffAttrs)
DECLARE_DYNAMIC_ATTRIBUTE(OnOff::Attributes::OnOff::Id, BOOLEAN, 1, 0), /* on/off */
    DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

// Descriptor attributes
DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(descriptorAttrs)
DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::DeviceTypeList::Id, ARRAY, kDescriptorAttributeArraySize, 0), /* device list */
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::ServerList::Id, ARRAY, kDescriptorAttributeArraySize, 0), /* server list */
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::ClientList::Id, ARRAY, kDescriptorAttributeArraySize, 0), /* client list */
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::PartsList::Id, ARRAY, kDescriptorAttributeArraySize, 0),  /* parts list */
#if CHIP_CONFIG_USE_ENDPOINT_UNIQUE_ID
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::EndpointUniqueID::Id, ARRAY, 32, 0), /* endpoint unique id*/
#endif
    DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

// Bridged Device Basic Information attributes
DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(bridgedDeviceBasicAttrs)
DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::NodeLabel::Id, CHAR_STRING, kNodeLabelSize, 0), /* NodeLabel */
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::Reachable::Id, BOOLEAN, 1, 0),              /* Reachable */
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::UniqueID::Id, CHAR_STRING, kUniqueIdSize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::ConfigurationVersion::Id, INT32U, 4, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::FeatureMap::Id, BITMAP32, 4, 0),
    DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

// On/Off command list
constexpr CommandId onOffIncomingCommands[] = {
    app::Clusters::OnOff::Commands::Off::Id,
    app::Clusters::OnOff::Commands::On::Id,
    app::Clusters::OnOff::Commands::Toggle::Id,
    app::Clusters::OnOff::Commands::OffWithEffect::Id,
    app::Clusters::OnOff::Commands::OnWithRecallGlobalScene::Id,
    app::Clusters::OnOff::Commands::OnWithTimedOff::Id,
    kInvalidCommandId,
};

// Cluster list for the bridged light
DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(bridgedLightClusters)
DECLARE_DYNAMIC_CLUSTER(OnOff::Id, onOffAttrs, ZAP_CLUSTER_MASK(SERVER), onOffIncomingCommands, nullptr),
    DECLARE_DYNAMIC_CLUSTER(Descriptor::Id, descriptorAttrs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(BridgedDeviceBasicInformation::Id, bridgedDeviceBasicAttrs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr)
    DECLARE_DYNAMIC_CLUSTER_LIST_END;

// Declare one bridged Light endpoint (ONLY ONE LIGHT)
DECLARE_DYNAMIC_ENDPOINT(bridgedLightEndpoint, bridgedLightClusters);
DataVersion gLight1DataVersions[MATTER_ARRAY_SIZE(bridgedLightClusters)];

// Create ONE light device object
DeviceOnOff Light1("Light 1", "Office");

} // namespace

// REVISION DEFINITIONS:
#define ZCL_DESCRIPTOR_CLUSTER_REVISION (1u)
#define ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_REVISION (2u)
#define ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_FEATURE_MAP (0u)
#define ZCL_ON_OFF_CLUSTER_REVISION (4u)

// ---------------- Attribute Read/Write handlers (keep minimal) ----------------

Protocols::InteractionModel::Status HandleReadBridgedDeviceBasicAttribute(Device * dev, chip::AttributeId attributeId,
                                                                          uint8_t * buffer, uint16_t maxReadLength)
{
    using namespace BridgedDeviceBasicInformation::Attributes;
    if ((attributeId == Reachable::Id) && (maxReadLength == 1))
    {
        *buffer = dev->IsReachable() ? 1 : 0;
    }
    else if ((attributeId == NodeLabel::Id) && (maxReadLength == 32))
    {
        MutableByteSpan zclNameSpan(buffer, maxReadLength);
        MakeZclCharString(zclNameSpan, dev->GetName());
    }
    else if ((attributeId == UniqueID::Id) && (maxReadLength == 32))
    {
        MutableByteSpan zclUniqueIdSpan(buffer, maxReadLength);
        MakeZclCharString(zclUniqueIdSpan, dev->GetUniqueId());
    }
    else if ((attributeId == ConfigurationVersion::Id) && (maxReadLength == 4))
    {
        uint32_t configVersion = dev->GetConfigurationVersion();
        memcpy(buffer, &configVersion, sizeof(configVersion));
    }
    else if ((attributeId == ClusterRevision::Id) && (maxReadLength == 2))
    {
        uint16_t rev = ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_REVISION;
        memcpy(buffer, &rev, sizeof(rev));
    }
    else if ((attributeId == FeatureMap::Id) && (maxReadLength == 4))
    {
        uint32_t featureMap = ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_FEATURE_MAP;
        memcpy(buffer, &featureMap, sizeof(featureMap));
    }
    else
    {
        return Protocols::InteractionModel::Status::Failure;
    }
    return Protocols::InteractionModel::Status::Success;
}

Protocols::InteractionModel::Status HandleReadOnOffAttribute(DeviceOnOff * dev, chip::AttributeId attributeId, uint8_t * buffer,
                                                             uint16_t maxReadLength)
{
    if ((attributeId == OnOff::Attributes::OnOff::Id) && (maxReadLength == 1))
    {
        *buffer = dev->IsOn() ? 1 : 0;
    }
    else if ((attributeId == OnOff::Attributes::ClusterRevision::Id) && (maxReadLength == 2))
    {
        uint16_t rev = ZCL_ON_OFF_CLUSTER_REVISION;
        memcpy(buffer, &rev, sizeof(rev));
    }
    else
    {
        return Protocols::InteractionModel::Status::Failure;
    }
    return Protocols::InteractionModel::Status::Success;
}

Protocols::InteractionModel::Status HandleWriteOnOffAttribute(DeviceOnOff * dev, chip::AttributeId attributeId, uint8_t * buffer)
{
    if ((attributeId == OnOff::Attributes::OnOff::Id) && (dev->IsReachable()))
    {
        const bool newOn = (*buffer != 0);

        // (A) Update local state quickly -> triggers reporting callbacks already wired
        dev->SetOnOff(newOn);

        // (B) Relay to your cloud (Flask) so your Python bulb actually changes
        postToCloudOnOff(newOn, dev->GetEndpointId());
    }
    else
    {
        return Protocols::InteractionModel::Status::Failure;
    }
    return Protocols::InteractionModel::Status::Success;
}

Protocols::InteractionModel::Status emberAfExternalAttributeReadCallback(EndpointId endpoint, ClusterId clusterId,
                                                                         const EmberAfAttributeMetadata * attributeMetadata,
                                                                         uint8_t * buffer, uint16_t maxReadLength)
{
    uint16_t endpointIndex = emberAfGetDynamicIndexFromEndpoint(endpoint);
    Protocols::InteractionModel::Status ret = Protocols::InteractionModel::Status::Failure;

    if ((endpointIndex < CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT) && (gDevices[endpointIndex] != nullptr))
    {
        Device * dev = gDevices[endpointIndex];

        if (clusterId == BridgedDeviceBasicInformation::Id)
        {
            ret = HandleReadBridgedDeviceBasicAttribute(dev, attributeMetadata->attributeId, buffer, maxReadLength);
        }
        else if (clusterId == OnOff::Id)
        {
            ret = HandleReadOnOffAttribute(static_cast<DeviceOnOff *>(dev), attributeMetadata->attributeId, buffer, maxReadLength);
        }
    }
    return ret;
}

void HandleDeviceStatusChanged(Device * dev, Device::Changed_t itemChangedMask)
{
    if (itemChangedMask & Device::kChanged_Reachable)
    {
        auto * path = Platform::New<app::ConcreteAttributePath>(dev->GetEndpointId(), BridgedDeviceBasicInformation::Id,
                                                                BridgedDeviceBasicInformation::Attributes::Reachable::Id);
        PlatformMgr().ScheduleWork([](intptr_t p) {
            auto path = reinterpret_cast<app::ConcreteAttributePath *>(p);
            MatterReportingAttributeChangeCallback(*path);
            Platform::Delete(path);
        }, reinterpret_cast<intptr_t>(path));
    }

    if (itemChangedMask & Device::kChanged_Name)
    {
        auto * path = Platform::New<app::ConcreteAttributePath>(dev->GetEndpointId(), BridgedDeviceBasicInformation::Id,
                                                                BridgedDeviceBasicInformation::Attributes::NodeLabel::Id);
        PlatformMgr().ScheduleWork([](intptr_t p) {
            auto path = reinterpret_cast<app::ConcreteAttributePath *>(p);
            MatterReportingAttributeChangeCallback(*path);
            Platform::Delete(path);
        }, reinterpret_cast<intptr_t>(path));
    }
}

void HandleDeviceOnOffStatusChanged(DeviceOnOff * dev, DeviceOnOff::Changed_t itemChangedMask)
{
    if (itemChangedMask & (DeviceOnOff::kChanged_Reachable | DeviceOnOff::kChanged_Name | DeviceOnOff::kChanged_Location))
    {
        HandleDeviceStatusChanged(static_cast<Device *>(dev), (Device::Changed_t) itemChangedMask);
    }

    if (itemChangedMask & DeviceOnOff::kChanged_OnOff)
    {
        auto * path =
            Platform::New<app::ConcreteAttributePath>(dev->GetEndpointId(), OnOff::Id, OnOff::Attributes::OnOff::Id);
        PlatformMgr().ScheduleWork([](intptr_t p) {
            auto path = reinterpret_cast<app::ConcreteAttributePath *>(p);
            MatterReportingAttributeChangeCallback(*path);
            Platform::Delete(path);
        }, reinterpret_cast<intptr_t>(path));
    }
}

// ---------------- App init: add ONLY ONE light endpoint ----------------

const EmberAfDeviceType gBridgedOnOffDeviceTypes[] = { { DEVICE_TYPE_LO_ON_OFF_LIGHT, DEVICE_VERSION_DEFAULT },
                                                       { DEVICE_TYPE_BRIDGED_NODE, DEVICE_VERSION_DEFAULT } };

int AddDeviceEndpoint(Device * dev, EmberAfEndpointType * ep, const Span<const EmberAfDeviceType> & deviceTypeList,
                      const Span<DataVersion> & dataVersionStorage,
#if CHIP_CONFIG_USE_ENDPOINT_UNIQUE_ID
                      chip::CharSpan epUniqueId,
#endif
                      chip::EndpointId parentEndpointId = chip::kInvalidEndpointId)
{
    uint8_t index = 0;
    while (index < CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT)
    {
        if (nullptr == gDevices[index])
        {
            gDevices[index] = dev;
            CHIP_ERROR err;
            while (true)
            {
                DeviceLayer::StackLock lock;
                dev->SetEndpointId(gCurrentEndpointId);
                dev->SetParentEndpointId(parentEndpointId);
#if !CHIP_CONFIG_USE_ENDPOINT_UNIQUE_ID
                err =
                    emberAfSetDynamicEndpoint(index, gCurrentEndpointId, ep, dataVersionStorage, deviceTypeList, parentEndpointId);
#else
                err = emberAfSetDynamicEndpointWithEpUniqueId(index, gCurrentEndpointId, ep, dataVersionStorage, deviceTypeList,
                                                              epUniqueId, parentEndpointId);
#endif
                if (err == CHIP_NO_ERROR)
                {
                    ChipLogProgress(DeviceLayer, "Added device %s to dynamic endpoint %d (index=%d)", dev->GetName(),
                                    gCurrentEndpointId, index);

                    if (dev->GetUniqueId()[0] == '\0')
                    {
                        dev->GenerateUniqueId();
                    }

                    return index;
                }
                if (err != CHIP_ERROR_ENDPOINT_EXISTS)
                {
                    gDevices[index] = nullptr;
                    return -1;
                }
                // Handle wrap condition
                if (++gCurrentEndpointId < gFirstDynamicEndpointId)
                {
                    gCurrentEndpointId = gFirstDynamicEndpointId;
                }
            }
        }
        index++;
    }
    ChipLogProgress(DeviceLayer, "Failed to add dynamic endpoint: No endpoints available!");
    return -1;
}

void ApplicationInit()
{
    // Clear device table
    memset(gDevices, 0, sizeof(gDevices));

    // Initialize our single light
    Light1.SetReachable(true);
    Light1.SetChangeCallback(&HandleDeviceOnOffStatusChanged);

    // Compute first dynamic endpoint id (next after last fixed one)
    gFirstDynamicEndpointId = static_cast<chip::EndpointId>(
        static_cast<int>(emberAfEndpointFromIndex(static_cast<uint16_t>(emberAfFixedEndpointCount() - 1))) + 1);
    gCurrentEndpointId = gFirstDynamicEndpointId;

    // Disable the dummy fixed endpoint (used to pull in cluster code)
    emberAfEndpointEnableDisable(
        emberAfEndpointFromIndex(static_cast<uint16_t>(emberAfFixedEndpointCount() - 1)), false);

    // ✅ Add ONLY ONE light endpoint
#if !CHIP_CONFIG_USE_ENDPOINT_UNIQUE_ID
    AddDeviceEndpoint(&Light1, &bridgedLightEndpoint, Span<const EmberAfDeviceType>(gBridgedOnOffDeviceTypes),
                      Span<DataVersion>(gLight1DataVersions), 1);
#else
    AddDeviceEndpoint(&Light1, &bridgedLightEndpoint, Span<const EmberAfDeviceType>(gBridgedOnOffDeviceTypes),
                      Span<DataVersion>(gLight1DataVersions), ""_span, 1);
#endif
}

void ApplicationShutdown() {}

int main(int argc, char * argv[])
{
    if (ChipLinuxAppInit(argc, argv) != 0)
    {
        return -1;
    }
    ChipLinuxAppMainLoop();
    return 0;
}

// ------- Named pipe command glue kept minimal (no-ops in this POC) -------
BridgeAppCommandHandler * BridgeAppCommandHandler::FromJSON(const char * json)
{
    Json::Reader reader;
    Json::Value value;

    if (!reader.parse(json, value))
    {
        ChipLogError(NotSpecified, "Bridge App: Error parsing JSON with error %s:", reader.getFormattedErrorMessages().c_str());
        return nullptr;
    }
    if (value.empty() || !value.isObject() || !value.isMember("Name") || !value["Name"].isString())
    {
        ChipLogError(NotSpecified, "Bridge App: Invalid JSON command received");
        return nullptr;
    }
    return Platform::New<BridgeAppCommandHandler>(std::move(value));
}

void BridgeAppCommandHandler::HandleCommand(intptr_t context)
{
    auto * self = reinterpret_cast<BridgeAppCommandHandler *>(context);
    std::string name = self->mJsonValue["Name"].asString();
    if (name == "SimulateConfigurationVersionChange")
    {
        uint32_t configVersion = Light1.GetConfigurationVersion() + 1;
        Light1.SetConfigurationVersion(configVersion);
    }
    else
    {
        ChipLogError(NotSpecified, "Unhandled command '%s'", name.c_str());
    }
    Platform::Delete(self);
}

void BridgeCommandDelegate::OnEventCommandReceived(const char * json)
{
    auto handler = BridgeAppCommandHandler::FromJSON(json);
    if (nullptr == handler)
    {
        ChipLogError(NotSpecified, "Bridge App: Unable to instantiate a command handler");
        return;
    }
    chip::DeviceLayer::PlatformMgr().ScheduleWork(BridgeAppCommandHandler::HandleCommand,
                                                  reinterpret_cast<intptr_t>(handler));
}
