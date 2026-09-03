package com.onrender.zipchatgo.property;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class MemberPropertyService {

    private final MemberPropertyRepository memberPropertyRepository;

    public MemberProperty register(Long memberId, PropertyRegisterRequest req) {
        MemberProperty property = new MemberProperty();
        property.setMemberId(memberId);
        property.setPropertyType(req.getPropertyType());
        property.setDealType(req.getDealType());
        property.setAddress1(req.getAddress1());
        property.setAddress2(req.getAddress2());
        property.setLatitude(req.getLatitude());
        property.setLongitude(req.getLongitude());
        property.setArea(req.getArea());
        property.setFloorInfo(req.getFloorInfo());
        property.setRooms(req.getRooms());
        property.setBaths(req.getBaths());
        property.setMaintenanceFee(req.getMaintenanceFee());
        property.setEtcFee(req.getEtcFee());
        property.setTransitInfo(req.getTransitInfo());
        property.setSchoolInfo(req.getSchoolInfo());
        property.setPrice(req.getPrice());
        property.setDeposit(req.getDeposit());
        property.setMonthly(req.getMonthly());
        property.setOwnerName(req.getOwnerName());
        property.setOwnerPhone(req.getOwnerPhone());
        property.setStatus("PENDING");

        Set<PropertyAttribute> attributes = new HashSet<>();
        addAttributes(attributes, "TAG", req.getTags());
        addAttributes(attributes, "OPTION", req.getOptions());
        addAttributes(attributes, "UTILITY", req.getUtilities());
        property.setAttributes(attributes);

        return memberPropertyRepository.save(property);
    }

    private void addAttributes(Set<PropertyAttribute> target, String category, List<String> values) {
        if (values == null) return;
        for (String v : values) {
            if (v == null || v.isBlank()) continue;
            target.add(new PropertyAttribute(null, category, v));
        }
    }
}
