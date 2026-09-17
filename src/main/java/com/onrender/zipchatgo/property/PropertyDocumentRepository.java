package com.onrender.zipchatgo.property;

import org.springframework.data.repository.CrudRepository;

import java.util.List;

public interface PropertyDocumentRepository extends CrudRepository<PropertyDocument, Long> {

    List<PropertyDocument> findByPropertyId(Long propertyId);
}
