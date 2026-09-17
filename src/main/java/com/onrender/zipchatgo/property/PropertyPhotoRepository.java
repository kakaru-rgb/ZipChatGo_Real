package com.onrender.zipchatgo.property;

import org.springframework.data.repository.CrudRepository;

import java.util.List;

public interface PropertyPhotoRepository extends CrudRepository<PropertyPhoto, Long> {

    List<PropertyPhoto> findByPropertyIdOrderByIdAsc(Long propertyId);
}
