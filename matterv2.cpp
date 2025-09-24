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
#include <app/server/Server.h>
#include <credentials/DeviceAttestationCredsProvider.h>
#include <credentials/examples/DeviceAttestationCredsExample.h>
#include <lib/core/CHIPError.h>
#include <lib/support/CHIPMem.h>
#include <lib/support/ZclString.h>
#include <platform/CommissionableDataProvider.h>
#include <setup_payload/QRCodeSetupPayloadGenerator.h>
#include <setup_payload/SetupPayload.h>

#include <cassert>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
#include <iterator>
#include <chrono>
#include <unistd.h>

#include "Device.h"

using namespace chip;
using namespace chip::app;
using namespace chip::Credentials;
using namespace chip::Inet;
using namespace chip::Transport;
using namespace chip::DeviceLayer;
using namespace chip::app::Clusters;

const int kNodeLabelSize = 32;
const int kUniqueIdSize  = 32;
const int kDescriptorAttributeArraySize = 254;

EndpointId gCurrentEndpointId;
EndpointId gFirstDynamicEndpointId;

Device * gDevices[CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT + 1] = {};

constexpr const char * kDefaultCloudURL = "https://www.cesieat.ovh/cloud";

#define DEVICE_TYPE_BRIDGED_NODE     0x0013
#define DEVICE_TYPE_LO_ON_OFF_LIGHT  0x0100
#define DEVICE_VERSION_DEFAULT 1

#define ZCL_DESCRIPTOR_CLUSTER_REVISION                       (1u)
#define ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_REVISION (2u)
#define ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_FEATURE_MAP      (0u)
#define ZCL_ON_OFF_CLUSTER_REVISION                           (4u)
#define ZCL_ON_OFF_FEATURE_MAP                                (0u)
#define ZCL_LEVEL_CONTROL_CLUSTER_REVISION                    (6u)
#define ZCL_LEVEL_CONTROL_FEATURE_MAP                         (0u)

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(onOffAttrs)
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::OnOff::Attributes::OnOff::Id, BOOLEAN, 1,
                              ZAP_ATTRIBUTE_MASK(WRITABLE) | ZAP_ATTRIBUTE_MASK(EXTERNAL_STORAGE)),
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::OnOff::Attributes::FeatureMap::Id, BITMAP32, 4, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::OnOff::Attributes::ClusterRevision::Id, INT16U, 2, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(levelControlAttrs)
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::LevelControl::Attributes::CurrentLevel::Id, INT8U, 1,
                              ZAP_ATTRIBUTE_MASK(WRITABLE) | ZAP_ATTRIBUTE_MASK(EXTERNAL_STORAGE)),
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::LevelControl::Attributes::MinLevel::Id, INT8U, 1, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::LevelControl::Attributes::MaxLevel::Id, INT8U, 1, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::LevelControl::Attributes::FeatureMap::Id, BITMAP32, 4, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::LevelControl::Attributes::Options::Id, BITMAP8, 1, ZAP_ATTRIBUTE_MASK(EXTERNAL_STORAGE)),
    DECLARE_DYNAMIC_ATTRIBUTE(::chip::app::Clusters::LevelControl::Attributes::ClusterRevision::Id, INT16U, 2, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(descriptorAttrs)
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::DeviceTypeList::Id, ARRAY, kDescriptorAttributeArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::ServerList::Id, ARRAY, kDescriptorAttributeArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::ClientList::Id, ARRAY, kDescriptorAttributeArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::PartsList::Id, ARRAY, kDescriptorAttributeArraySize, 0),
#if CHIP_CONFIG_USE_ENDPOINT_UNIQUE_ID
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::EndpointUniqueID::Id, ARRAY, 32, 0),
#endif
    DECLARE_DYNAMIC_ATTRIBUTE(Descriptor::Attributes::ClusterRevision::Id, INT16U, 2, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(bridgedDeviceBasicAttrs)
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::NodeLabel::Id, CHAR_STRING, kNodeLabelSize,
                              ZAP_ATTRIBUTE_MASK(WRITABLE) | ZAP_ATTRIBUTE_MASK(EXTERNAL_STORAGE)),
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::Reachable::Id, BOOLEAN, 1,
                              ZAP_ATTRIBUTE_MASK(EXTERNAL_STORAGE)),
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::UniqueID::Id, CHAR_STRING, kUniqueIdSize,
                              ZAP_ATTRIBUTE_MASK(EXTERNAL_STORAGE)),
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::ConfigurationVersion::Id, INT32U, 4,
                              ZAP_ATTRIBUTE_MASK(EXTERNAL_STORAGE)),
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::FeatureMap::Id, BITMAP32, 4, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(BridgedDeviceBasicInformation::Attributes::ClusterRevision::Id, INT16U, 2, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

constexpr CommandId onOffIncomingCommands[] = {
    app::Clusters::OnOff::Commands::Off::Id,
    app::Clusters::OnOff::Commands::On::Id,
    app::Clusters::OnOff::Commands::Toggle::Id,
    app::Clusters::OnOff::Commands::OffWithEffect::Id,
    app::Clusters::OnOff::Commands::OnWithRecallGlobalScene::Id,
    app::Clusters::OnOff::Commands::OnWithTimedOff::Id,
    kInvalidCommandId,
};

constexpr CommandId levelControlIncomingCommands[] = {
    ::chip::app::Clusters::LevelControl::Commands::MoveToLevel::Id,
    ::chip::app::Clusters::LevelControl::Commands::Move::Id,
    ::chip::app::Clusters::LevelControl::Commands::Step::Id,
    ::chip::app::Clusters::LevelControl::Commands::Stop::Id,
    ::chip::app::Clusters::LevelControl::Commands::MoveToLevelWithOnOff::Id,
    ::chip::app::Clusters::LevelControl::Commands::MoveWithOnOff::Id,
    ::chip::app::Clusters::LevelControl::Commands::StepWithOnOff::Id,
    ::chip::app::Clusters::LevelControl::Commands::StopWithOnOff::Id,
    kInvalidCommandId,
};

DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(bridgedLightClusters)
    DECLARE_DYNAMIC_CLUSTER(::chip::app::Clusters::OnOff::Id, onOffAttrs,
                            ZAP_CLUSTER_MASK(SERVER), onOffIncomingCommands, nullptr),
    DECLARE_DYNAMIC_CLUSTER(::chip::app::Clusters::LevelControl::Id, levelControlAttrs,
                            ZAP_CLUSTER_MASK(SERVER), levelControlIncomingCommands, nullptr),
    DECLARE_DYNAMIC_CLUSTER(Descriptor::Id, descriptorAttrs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(BridgedDeviceBasicInformation::Id, bridgedDeviceBasicAttrs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr)
DECLARE_DYNAMIC_CLUSTER_LIST_END;

DECLARE_DYNAMIC_ENDPOINT(bridgedLightEndpoint, bridgedLightClusters);
DataVersion gLight1DataVersions[MATTER_ARRAY_SIZE(bridgedLightClusters)];

DeviceOnOff Light1("Light 1", "Office");

const EmberAfDeviceType gBridgedOnOffDeviceTypes[] = {
    { DEVICE_TYPE_LO_ON_OFF_LIGHT, DEVICE_VERSION_DEFAULT },
    { DEVICE_TYPE_BRIDGED_NODE,    DEVICE_VERSION_DEFAULT }
};

static std::string MakeIdempotencyKey()
{
    using namespace std::chrono;
    auto now = duration_cast<nanoseconds>(steady_clock::now().time_since_epoch()).count();
    return std::to_string(getpid()) + "-" + std::to_string(now);
}

static void patchCloudEnabled(bool on)
{
    const char * url = std::getenv("CLOUD_URL");
    if (!url || !*url) url = kDefaultCloudURL;

    const char * apiKey = std::getenv("CLOUD_API_KEY");

    std::string jsonBody = std::string("{\"enabled\":") + (on ? "true" : "false") + "}";
    std::string idem = MakeIdempotencyKey();

    std::string cmd = "curl -s -X PATCH ";
    cmd += "-H 'Content-Type: application/json' ";
    cmd += "-H 'Idempotency-Key: " + idem + "' ";
    if (apiKey && *apiKey)
    {
        cmd += "-H 'X-API-Key: ";
        cmd += apiKey;
        cmd += "' ";
    }
    cmd += "--max-time 5 ";
    cmd += "--data '" + jsonBody + "' ";
    cmd += url;
    cmd += " >/dev/null 2>&1";

    int rc = std::system(cmd.c_str());
    if (rc != 0)
    {
        ChipLogError(NotSpecified, "Cloud PATCH failed (rc=%d) for URL: %s", rc, url);
    }
    else
    {
        ChipLogProgress(NotSpecified, "Cloud PATCH succeeded: %s enabled=%s", url, on ? "true" : "false");
    }
}

static void patchCloudBrightness(uint8_t level)
{
    const char * url = std::getenv("CLOUD_URL");
    if (!url || !*url) url = kDefaultCloudURL;

    const char * apiKey = std::getenv("CLOUD_API_KEY");

    std::string jsonBody = std::string("{\"brightness\":") + std::to_string(level) + "}";
    std::string idem = MakeIdempotencyKey();

    std::string cmd = "curl -s -X PATCH ";
    cmd += "-H 'Content-Type: application/json' ";
    cmd += "-H 'Idempotency-Key: " + idem + "' ";
    if (apiKey && *apiKey)
    {
        cmd += "-H 'X-API-Key: ";
        cmd += apiKey;
        cmd += "' ";
    }
    cmd += "--max-time 5 ";
    cmd += "--data '" + jsonBody + "' ";
    cmd += url;
    cmd += " >/dev/null 2>&1";

    int rc = std::system(cmd.c_str());
    if (rc != 0)
    {
        ChipLogError(NotSpecified, "Cloud PATCH (brightness) failed (rc=%d) for URL: %s", rc, url);
    }
    else
    {
        ChipLogProgress(NotSpecified, "Cloud PATCH (brightness) succeeded: %s brightness=%u", url, (unsigned) level);
    }
}

int AddDeviceEndpoint(Device * dev,
                      EmberAfEndpointType * ep,
                      const Span<const EmberAfDeviceType> & deviceTypeList,
                      const Span<DataVersion> & dataVersionStorage
#if CHIP_CONFIG_USE_ENDPOINT_UNIQUE_ID
                      , chip::CharSpan epUniqueId
#endif
                      , chip::EndpointId parentEndpointId = chip::kInvalidEndpointId)
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
                err = emberAfSetDynamicEndpoint(index, gCurrentEndpointId, ep, dataVersionStorage, deviceTypeList, parentEndpointId);
#else
                err = emberAfSetDynamicEndpointWithEpUniqueId(index, gCurrentEndpointId, ep, dataVersionStorage, deviceTypeList,
                                                              epUniqueId, parentEndpointId);
#endif
                if (err == CHIP_NO_ERROR)
                {
                    ChipLogProgress(DeviceLayer, "Added device %s to dynamic endpoint %d (index=%d)",
                                    dev->GetName(), gCurrentEndpointId, index);

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

void HandleDeviceStatusChanged(Device * dev, Device::Changed_t itemChangedMask)
{
    if (itemChangedMask & Device::kChanged_Reachable)
    {
        auto * attrPath = Platform::New<app::ConcreteAttributePath>(
            dev->GetEndpointId(),
            BridgedDeviceBasicInformation::Id,
            BridgedDeviceBasicInformation::Attributes::Reachable::Id);
        PlatformMgr().ScheduleWork([](intptr_t closure) {
            auto attrPathFromClosure = reinterpret_cast<app::ConcreteAttributePath *>(closure);
            MatterReportingAttributeChangeCallback(*attrPathFromClosure);
            Platform::Delete(attrPathFromClosure);
        }, reinterpret_cast<intptr_t>(attrPath));
    }

    if (itemChangedMask & Device::kChanged_Name)
    {
        auto * attrPath = Platform::New<app::ConcreteAttributePath>(
            dev->GetEndpointId(),
            BridgedDeviceBasicInformation::Id,
            BridgedDeviceBasicInformation::Attributes::NodeLabel::Id);
        PlatformMgr().ScheduleWork([](intptr_t closure) {
            auto attrPathFromClosure = reinterpret_cast<app::ConcreteAttributePath *>(closure);
            MatterReportingAttributeChangeCallback(*attrPathFromClosure);
            Platform::Delete(attrPathFromClosure);
        }, reinterpret_cast<intptr_t>(attrPath));
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
        auto * attrPath = Platform::New<app::ConcreteAttributePath>(
            dev->GetEndpointId(), ::chip::app::Clusters::OnOff::Id,
            ::chip::app::Clusters::OnOff::Attributes::OnOff::Id);
        PlatformMgr().ScheduleWork([](intptr_t closure) {
            auto * p = reinterpret_cast<app::ConcreteAttributePath *>(closure);
            MatterReportingAttributeChangeCallback(*p);
            Platform::Delete(p);
        }, reinterpret_cast<intptr_t>(attrPath));
    }
    if (itemChangedMask & DeviceOnOff::kChanged_Level)
    {
        auto * attrPath = Platform::New<app::ConcreteAttributePath>(
            dev->GetEndpointId(), ::chip::app::Clusters::LevelControl::Id,
            ::chip::app::Clusters::LevelControl::Attributes::CurrentLevel::Id);
        PlatformMgr().ScheduleWork([](intptr_t closure) {
            auto * p = reinterpret_cast<app::ConcreteAttributePath *>(closure);
            MatterReportingAttributeChangeCallback(*p);
            Platform::Delete(p);
        }, reinterpret_cast<intptr_t>(attrPath));
    }
}

static DeviceOnOff * GetOnOffDevice(chip::EndpointId endpoint)
{
    uint16_t idx = emberAfGetDynamicIndexFromEndpoint(endpoint);
    if (idx >= (CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT + 1) || gDevices[idx] == nullptr)
        return nullptr;
    return static_cast<DeviceOnOff *>(gDevices[idx]);
}

Protocols::InteractionModel::Status HandleReadBridgedDeviceBasicAttribute(Device * dev,
                                                                          chip::AttributeId attributeId,
                                                                          uint8_t * buffer,
                                                                          uint16_t maxReadLength)
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

Protocols::InteractionModel::Status HandleReadOnOffAttribute(DeviceOnOff * dev,
                                                             chip::AttributeId attributeId,
                                                             uint8_t * buffer,
                                                             uint16_t maxReadLength)
{
    if ((attributeId == ::chip::app::Clusters::OnOff::Attributes::OnOff::Id) && (maxReadLength == 1))
    {
        *buffer = dev->IsOn() ? 1 : 0;
    }
    else if ((attributeId == ::chip::app::Clusters::OnOff::Attributes::ClusterRevision::Id) && (maxReadLength == 2))
